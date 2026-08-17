"""Clean the raw conditions.csv extract and load it into Postgres.

conditions hangs off the encounters fact table: one row per diagnosis recorded
at a visit. The file has no id column of its own, so a row is identified by
the combination PATIENT + ENCOUNTER + CODE + START.

Issues found in the raw extract (4,748 rows):
  - STOP is empty on 1,121 rows. That is not missing data: it means the
    condition is still active, so it stays null and gets an is_ongoing flag.
  - DESCRIPTION ends with a clinical qualifier in brackets, for example
    "Acute bronchitis (disorder)". That qualifier is a category, not part of
    the name, so it is split into its own column.
  - SYSTEM is the same SNOMED URL on every row.
  - CODE is read as an integer, but a clinical code is an identifier that
    happens to be numeric, so it belongs in a text column.

Run on its own:
    python etl/clean_conditions.py

Or run all six cleaners at once:
    python etl/load_nexora.py
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Read .env once when this file is imported, so the database password lives
# there and never inside a .py file.
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")

# Folder holding the raw CSVs. Point DATA_DIR at data/incoming/week_01 in .env
# to clean a weekly batch instead of the original extract.
SOURCE_DIR = project_root / os.getenv("DATA_DIR", "data/source")


def cleaning_conditions_data(source_dir=SOURCE_DIR, engine=None):
    """Clean conditions.csv and load it into the conditions_clean table."""
    if engine is None:
        engine = create_engine(os.getenv("DATABASE_URL"))

    print("Starting the ETL process for cleaning conditions data...")

    # Read CODE as text from the start so it is never treated as a number.
    df_conditions = pd.read_csv(source_dir / "conditions.csv", dtype={"CODE": str})
    rows_read = len(df_conditions)
    print(f"Read {rows_read} rows from conditions.csv")

    # Trim both foreign keys down to the last part of the UUID, matching the
    # rule used by clean_patients.py and clean_encounters.py.
    for col in ["PATIENT", "ENCOUNTER"]:
        df_conditions[col] = df_conditions[col].str.strip().str.lower().str.split("-").str[-1]

    # START and STOP are plain dates with no time part, so keep them as dates.
    # Anything unreadable is coerced to NaT rather than crashing the run.
    df_conditions["START"] = pd.to_datetime(df_conditions["START"], errors="coerce")
    df_conditions["STOP"] = pd.to_datetime(df_conditions["STOP"], errors="coerce")

    # SYSTEM is "http://snomed.info/sct" on every row. Keep the column, because a
    # future extract could mix in ICD-10 codes, but store the readable short name.
    df_conditions["SYSTEM"] = (
        df_conditions["SYSTEM"].str.strip().replace({"http://snomed.info/sct": "SNOMED-CT"})
    )

    # Strip any stray ".0" that a numeric read could leave behind on the code.
    df_conditions["CODE"] = (
        df_conditions["CODE"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )

    # Split the trailing bracketed qualifier off the description into its own
    # column: "Acute bronchitis (disorder)" becomes "Acute bronchitis" + "Disorder".
    # The 8 rows with no bracket get "Unspecified" so the column is never null.
    df_conditions["CONDITION_CATEGORY"] = (
        df_conditions["DESCRIPTION"].str.extract(r"\(([^()]*)\)\s*$")[0].str.title()
    )
    df_conditions["CONDITION_CATEGORY"] = df_conditions["CONDITION_CATEGORY"].fillna("Unspecified")

    df_conditions["DESCRIPTION"] = (
        df_conditions["DESCRIPTION"]
        .str.replace(r"\s*\([^()]*\)\s*$", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # An empty STOP means the condition has not been resolved yet, so record that
    # as a flag rather than inventing a fake end date.
    df_conditions["IS_ONGOING"] = df_conditions["STOP"].isna()

    # How long the condition was open. This stays null for ongoing conditions,
    # which is exactly what we want: an unresolved condition has no duration yet.
    df_conditions["DURATION_DAYS"] = (df_conditions["STOP"] - df_conditions["START"]).dt.days

    # A condition cannot be resolved before it started. Drop those rows rather than
    # loading a negative duration into the warehouse.
    rows_before = len(df_conditions)
    df_conditions = df_conditions[
        df_conditions["STOP"].isna() | (df_conditions["STOP"] >= df_conditions["START"])
    ]
    bad_chronology = rows_before - len(df_conditions)

    # A diagnosis with no start date, patient or encounter cannot be placed in the
    # star schema at all.
    rows_before = len(df_conditions)
    df_conditions = df_conditions[
        df_conditions["START"].notna()
        & df_conditions["PATIENT"].notna()
        & df_conditions["ENCOUNTER"].notna()
        & df_conditions["CODE"].notna()
    ]
    dropped_incomplete = rows_before - len(df_conditions)

    # The same diagnosis must not be recorded twice for one visit. This matches the
    # UNIQUE (patient_id, encounter_id, code, start_date) constraint on the table,
    # so de-duplicating here stops the load from failing on it.
    duplicate_rows = int(
        df_conditions.duplicated(subset=["PATIENT", "ENCOUNTER", "CODE", "START"]).sum()
    )
    df_conditions.drop_duplicates(
        subset=["PATIENT", "ENCOUNTER", "CODE", "START"], keep="first", inplace=True
    )

    # Rename the columns to lowercase snake_case to match the Postgres convention.
    df_conditions.rename(
        columns={
            "PATIENT": "patient_id",
            "ENCOUNTER": "encounter_id",
            "SYSTEM": "code_system",
            "CODE": "code",
            "DESCRIPTION": "description",
            "CONDITION_CATEGORY": "condition_category",
            "START": "start_date",
            "STOP": "stop_date",
            "IS_ONGOING": "is_ongoing",
            "DURATION_DAYS": "duration_days",
        },
        inplace=True,
    )

    new_col = [
        "patient_id", "encounter_id", "code_system", "code", "description",
        "condition_category", "start_date", "stop_date", "is_ongoing", "duration_days",
    ]
    df_conditions = df_conditions.loc[:, new_col]

    # "replace" keeps this script re-runnable: running it twice never doubles the rows.
    df_conditions.to_sql("conditions_clean", engine, if_exists="replace", index=False)

    rejected = duplicate_rows + bad_chronology + dropped_incomplete
    print(f"Dropped {duplicate_rows} duplicate, {bad_chronology} out-of-order "
          f"and {dropped_incomplete} incomplete row(s)")
    print(f"Loaded {len(df_conditions)} of {rows_read} rows into 'conditions_clean'.")
    print(f"{int(df_conditions['is_ongoing'].sum())} condition(s) are still ongoing.")

    # load_nexora.py uses these numbers for its summary and its audit table.
    return {
        "dataset": "conditions",
        "rows_read": rows_read,
        "rows_loaded": len(df_conditions),
        "rows_rejected": rejected,
    }


if __name__ == "__main__":
    cleaning_conditions_data()
