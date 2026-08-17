"""Clean the raw payers.csv extract and load it into Postgres.

payers is a dimension of the star schema: one row per insurer that can be
billed for an encounter. Only 10 rows, but every encounter points at one.

Issues found in the raw extract (10 rows, 22 columns):
  - ADDRESS, CITY, STATE_HEADQUARTERED, ZIP and PHONE are empty on all 10
    rows, so pandas typed them as float64 columns full of NaN.
  - NAME uses the machine token "NO_INSURANCE" for self-paying patients.
  - OWNERSHIP is uppercase and also uses the "NO_INSURANCE" token.

Run on its own:
    python etl/clean_payers.py

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


def cleaning_payers_data(source_dir=SOURCE_DIR, engine=None):
    """Clean payers.csv and load it into the payers_clean table.

    Both arguments are optional, so this still works when the file is run on
    its own. load_nexora.py passes in its own folder and database connection.
    """
    if engine is None:
        engine = create_engine(os.getenv("DATABASE_URL"))

    print("Starting the ETL process for cleaning payers data...")

    df_payers = pd.read_csv(source_dir / "payers.csv")
    rows_read = len(df_payers)
    print(f"Read {rows_read} rows from payers.csv")

    # Trim the id down to the last part of the UUID, the same way every other
    # cleaner does. "b77f00240d82" is far easier to read in a query result than
    # the full id. This only works because it is done everywhere: encounters
    # trims its PAYER column too, so the two still match up.
    df_payers["Id"] = df_payers["Id"].str.strip().str.lower().str.split("-").str[-1]

    # These five columns are empty on all 10 rows, so there is nothing to clean and
    # nothing to keep. Carrying an all-NaN column into the warehouse just invites
    # someone to join on it later.
    df_payers.drop(
        columns=["ADDRESS", "CITY", "STATE_HEADQUARTERED", "ZIP", "PHONE"], inplace=True
    )

    # NAME is already human readable apart from the self-pay token. Do NOT title
    # case this column: it would turn "UnitedHealthcare" into "Unitedhealthcare"
    # and "Blue Cross Blue Shield" is already correct.
    df_payers["NAME"] = df_payers["NAME"].str.strip()
    df_payers["NAME"] = df_payers["NAME"].replace({"NO_INSURANCE": "No Insurance"})

    # OWNERSHIP is a small uppercase category, so swap the underscore for a space
    # and title case it: GOVERNMENT -> Government, NO_INSURANCE -> No Insurance.
    df_payers["OWNERSHIP"] = (
        df_payers["OWNERSHIP"].str.strip().str.replace("_", " ", regex=False).str.title()
    )

    # Every remaining column is a money amount or a count. Force them to numbers so
    # a stray "N/A" in a future weekly batch becomes NaN instead of poisoning the
    # whole column into text.
    money_cols = ["AMOUNT_COVERED", "AMOUNT_UNCOVERED", "REVENUE", "QOLS_AVG"]
    for col in money_cols:
        df_payers[col] = pd.to_numeric(df_payers[col], errors="coerce").round(2)

    count_cols = [
        "COVERED_ENCOUNTERS", "UNCOVERED_ENCOUNTERS",
        "COVERED_MEDICATIONS", "UNCOVERED_MEDICATIONS",
        "COVERED_PROCEDURES", "UNCOVERED_PROCEDURES",
        "COVERED_IMMUNIZATIONS", "UNCOVERED_IMMUNIZATIONS",
        "UNIQUE_CUSTOMERS", "MEMBER_MONTHS",
    ]
    for col in count_cols:
        df_payers[col] = pd.to_numeric(df_payers[col], errors="coerce").fillna(0).astype(int)

    # Share of billed money this payer actually covered. Guard against a zero
    # denominator so a payer with no billing does not produce an infinity.
    total_billed = df_payers["AMOUNT_COVERED"] + df_payers["AMOUNT_UNCOVERED"]
    df_payers["COVERAGE_RATE"] = (
        (df_payers["AMOUNT_COVERED"] / total_billed).where(total_billed > 0).round(4)
    )

    # A payer can only appear once, so keep the first row per id.
    duplicate_ids = int(df_payers["Id"].duplicated().sum())
    df_payers.drop_duplicates(subset=["Id"], keep="first", inplace=True)

    # A payer with no name is unusable as a dimension record.
    rows_before = len(df_payers)
    df_payers = df_payers[df_payers["NAME"].notna() & (df_payers["NAME"].str.strip() != "")]
    missing_name = rows_before - len(df_payers)

    # Rename the columns to lowercase snake_case to match the Postgres convention.
    df_payers.rename(columns={"Id": "id"}, inplace=True)
    df_payers.columns = df_payers.columns.str.lower()

    new_col = [
        "id", "name", "ownership", "amount_covered", "amount_uncovered", "coverage_rate",
        "revenue", "covered_encounters", "uncovered_encounters",
        "covered_medications", "uncovered_medications",
        "covered_procedures", "uncovered_procedures",
        "covered_immunizations", "uncovered_immunizations",
        "unique_customers", "qols_avg", "member_months",
    ]
    df_payers = df_payers.loc[:, new_col]

    # "replace" keeps this script re-runnable: running it twice never doubles the rows.
    df_payers.to_sql("payers_clean", engine, if_exists="replace", index=False)

    print(f"Dropped {duplicate_ids} duplicate id(s) and {missing_name} unnamed row(s)")
    print(f"Loaded {len(df_payers)} of {rows_read} rows into 'payers_clean'.")

    # load_nexora.py uses these numbers for its summary and its audit table.
    return {
        "dataset": "payers",
        "rows_read": rows_read,
        "rows_loaded": len(df_payers),
        "rows_rejected": duplicate_ids + missing_name,
    }


if __name__ == "__main__":
    cleaning_payers_data()
