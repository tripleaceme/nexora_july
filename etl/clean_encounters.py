"""Clean the raw encounters.csv extract and load it into Postgres.

encounters is the fact table at the centre of the star schema: one row per
appointment, pointing at a patient, an organization, a provider and a payer.
Load this AFTER the four dimension files, because it references all of them.

Issues found in the raw extract (7,210 rows):
  - START and STOP are ISO 8601 strings ending in "Z", so they must be parsed
    as UTC rather than left as naive text.
  - REASONCODE is empty on 2,949 rows, which made pandas read the whole column
    as a float and print clinical codes as "10509002.0".
  - DESCRIPTION ends with a bracketed qualifier, e.g. "(procedure)".
  - CODE is read as an integer, but a clinical code is an identifier.

Note on ENCOUNTERCLASS: the star schema encounters table has a CHECK that
restricts it to a fixed lowercase list, so this column is deliberately NOT
title cased. Values outside the list are rejected instead.

Run on its own:
    python etl/clean_encounters.py

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

# The only encounter classes the warehouse accepts, copied from the CHECK
# constraint on the encounters table.
ALLOWED_CLASSES = [
    "ambulatory", "wellness", "outpatient", "urgentcare", "emergency",
    "inpatient", "home", "snf", "hospice", "virtual",
]


def cleaning_encounters_data(source_dir=SOURCE_DIR, engine=None):
    """Clean encounters.csv and load it into the encounters_clean table."""
    if engine is None:
        engine = create_engine(os.getenv("DATABASE_URL"))

    print("Starting the ETL process for cleaning encounters data...")

    # Read the clinical codes as text from the start so they are never numbers.
    df_encounters = pd.read_csv(
        source_dir / "encounters.csv", dtype={"CODE": str, "REASONCODE": str}
    )
    rows_read = len(df_encounters)
    print(f"Read {rows_read} rows from encounters.csv")

    # Trim all five ids down to the last part of the UUID. These four foreign
    # keys are the reason the trimming rule has to be identical everywhere: if
    # one dimension cleaner kept the full id, its join would return nothing and
    # nothing would raise an error to tell you.
    for col in ["Id", "PATIENT", "ORGANIZATION", "PROVIDER", "PAYER"]:
        df_encounters[col] = df_encounters[col].str.strip().str.lower().str.split("-").str[-1]

    # The timestamps end in "Z", so parse them as UTC. Storing an appointment time
    # without its timezone is how reports end up an hour out.
    df_encounters["START"] = pd.to_datetime(df_encounters["START"], errors="coerce", utc=True)
    df_encounters["STOP"] = pd.to_datetime(df_encounters["STOP"], errors="coerce", utc=True)

    # How long the appointment lasted, which is the obvious thing to ask of a fact
    # table and is much cheaper to compute once here than in every query.
    df_encounters["DURATION_MINUTES"] = (
        (df_encounters["STOP"] - df_encounters["START"]).dt.total_seconds() / 60
    ).round(1)

    # ENCOUNTERCLASS is a controlled vocabulary, so only lowercase and trim it.
    # Title casing it here would break the CHECK constraint on the table.
    df_encounters["ENCOUNTERCLASS"] = df_encounters["ENCOUNTERCLASS"].str.strip().str.lower()

    # Strip any stray ".0" left behind on the clinical codes, then split the
    # trailing bracketed qualifier off the description into its own column:
    # "Well child visit (procedure)" becomes "Well child visit" + "Procedure".
    df_encounters["CODE"] = (
        df_encounters["CODE"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )

    df_encounters["DESCRIPTION_TYPE"] = (
        df_encounters["DESCRIPTION"].str.extract(r"\(([^()]*)\)\s*$")[0].str.title()
    )
    df_encounters["DESCRIPTION_TYPE"] = df_encounters["DESCRIPTION_TYPE"].fillna("Unspecified")

    df_encounters["DESCRIPTION"] = (
        df_encounters["DESCRIPTION"]
        .str.replace(r"\s*\([^()]*\)\s*$", "", regex=True)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # REASONCODE is blank on 2,949 rows. Reading it as text keeps the code intact
    # instead of printing it as "10509002.0", and the blank rows simply mean the
    # visit had no recorded reason.
    df_encounters["REASONCODE"] = (
        df_encounters["REASONCODE"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )
    df_encounters["REASONCODE"] = df_encounters["REASONCODE"].replace({"nan": None, "": None})
    df_encounters["REASONDESCRIPTION"] = df_encounters["REASONDESCRIPTION"].fillna("Not Specified")

    # Force the money columns to numbers. A stray "N/A" in a weekly batch becomes
    # NaN here instead of turning the whole column into text.
    for col in ["BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "PAYER_COVERAGE"]:
        df_encounters[col] = pd.to_numeric(df_encounters[col], errors="coerce").round(2)

    # What the patient was left to pay, and what share the insurer picked up.
    # These two are the whole point of the case study's coverage questions.
    df_encounters["UNCOVERED_AMOUNT"] = (
        df_encounters["TOTAL_CLAIM_COST"] - df_encounters["PAYER_COVERAGE"]
    ).round(2)
    df_encounters["COVERAGE_RATE"] = (
        (df_encounters["PAYER_COVERAGE"] / df_encounters["TOTAL_CLAIM_COST"])
        .where(df_encounters["TOTAL_CLAIM_COST"] > 0)
        .round(4)
    )

    # An encounter can only appear once, so keep the first row per id.
    duplicate_ids = int(df_encounters["Id"].duplicated().sum())
    df_encounters.drop_duplicates(subset=["Id"], keep="first", inplace=True)

    # An appointment cannot finish before it starts. The dirty batch generator
    # injects exactly this by swapping START and STOP.
    rows_before = len(df_encounters)
    df_encounters = df_encounters[
        df_encounters["STOP"].isna() | (df_encounters["STOP"] >= df_encounters["START"])
    ]
    bad_chronology = rows_before - len(df_encounters)

    # An encounter class outside the allowed list would be rejected by the table's
    # CHECK constraint, so drop it here where we can count it.
    rows_before = len(df_encounters)
    df_encounters = df_encounters[df_encounters["ENCOUNTERCLASS"].isin(ALLOWED_CLASSES)]
    bad_class = rows_before - len(df_encounters)

    # A fact row is useless without its start time or its dimension keys.
    rows_before = len(df_encounters)
    df_encounters = df_encounters[
        df_encounters["Id"].notna()
        & df_encounters["START"].notna()
        & df_encounters["PATIENT"].notna()
        & df_encounters["ORGANIZATION"].notna()
        & df_encounters["PROVIDER"].notna()
    ]
    dropped_incomplete = rows_before - len(df_encounters)

    # Rename the columns to lowercase snake_case to match the Postgres convention.
    df_encounters.rename(
        columns={
            "Id": "id",
            "START": "start_ts",
            "STOP": "stop_ts",
            "DURATION_MINUTES": "duration_minutes",
            "PATIENT": "patient_id",
            "ORGANIZATION": "organization_id",
            "PROVIDER": "provider_id",
            "PAYER": "payer_id",
            "ENCOUNTERCLASS": "encounter_class",
            "CODE": "code",
            "DESCRIPTION": "description",
            "DESCRIPTION_TYPE": "description_type",
            "REASONCODE": "reason_code",
            "REASONDESCRIPTION": "reason_description",
            "BASE_ENCOUNTER_COST": "base_encounter_cost",
            "TOTAL_CLAIM_COST": "total_claim_cost",
            "PAYER_COVERAGE": "payer_coverage",
            "UNCOVERED_AMOUNT": "uncovered_amount",
            "COVERAGE_RATE": "coverage_rate",
        },
        inplace=True,
    )

    new_col = [
        "id", "patient_id", "organization_id", "provider_id", "payer_id",
        "start_ts", "stop_ts", "duration_minutes", "encounter_class",
        "code", "description", "description_type", "reason_code", "reason_description",
        "base_encounter_cost", "total_claim_cost", "payer_coverage",
        "uncovered_amount", "coverage_rate",
    ]
    df_encounters = df_encounters.loc[:, new_col]

    # "replace" keeps this script re-runnable: running it twice never doubles the rows.
    df_encounters.to_sql("encounters_clean", engine, if_exists="replace", index=False)

    rejected = duplicate_ids + bad_chronology + bad_class + dropped_incomplete
    print(f"Dropped {duplicate_ids} duplicate, {bad_chronology} out-of-order, "
          f"{bad_class} bad-class and {dropped_incomplete} incomplete row(s)")
    print(f"Loaded {len(df_encounters)} of {rows_read} rows into 'encounters_clean'.")

    # load_nexora.py uses these numbers for its summary and its audit table.
    return {
        "dataset": "encounters",
        "rows_read": rows_read,
        "rows_loaded": len(df_encounters),
        "rows_rejected": rejected,
    }


if __name__ == "__main__":
    cleaning_encounters_data()
