"""Clean the raw organizations.csv extract and load it into Postgres.

organizations is a dimension of the star schema: one row per clinic or
hospital that an encounter can happen at.

Issues found in the raw extract (283 rows):
  - ZIP was written as a number, so the leading Massachusetts "0" was lost.
    274 rows are 8 digits (ZIP5 + ZIP4 run together), 9 rows are 4 digits.
  - NAME and ADDRESS are almost all SHOUTED UPPERCASE with double spaces.
  - One PHONE holds the same number twice ("978-342-9781 Or 978-342-9781").
  - REVENUE is 0.0 on every row, so it carries no information.

Run on its own:
    python etl/clean_organizations.py

Or run all six cleaners at once:
    python etl/load_nexora.py
"""

import os
from pathlib import Path

import numpy as np
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


def cleaning_organizations_data(source_dir=SOURCE_DIR, engine=None):
    """Clean organizations.csv and load it into the organizations_clean table."""
    if engine is None:
        engine = create_engine(os.getenv("DATABASE_URL"))

    print("Starting the ETL process for cleaning organizations data...")

    # Read ZIP as text so pandas cannot strip the leading zero a second time.
    df_organizations = pd.read_csv(source_dir / "organizations.csv", dtype={"ZIP": str})
    rows_read = len(df_organizations)
    print(f"Read {rows_read} rows from organizations.csv")

    # Trim the id down to the last part of the UUID so it is readable in query
    # results. providers.ORGANIZATION and encounters.ORGANIZATION are trimmed
    # the same way, which is what keeps those links working.
    df_organizations["Id"] = (
        df_organizations["Id"].str.strip().str.lower().str.split("-").str[-1]
    )

    # Collapse the double spaces, trim the ends, then title case the shouted names.
    df_organizations["NAME"] = (
        df_organizations["NAME"].str.replace(r"\s+", " ", regex=True).str.strip().str.title()
    )
    df_organizations["ADDRESS"] = (
        df_organizations["ADDRESS"].str.replace(r"\s+", " ", regex=True).str.strip().str.title()
    )
    df_organizations["CITY"] = (
        df_organizations["CITY"].str.replace(r"\s+", " ", regex=True).str.strip().str.title()
    )

    # Title case turns "LLC" into "Llc", which reads as a typo, so put the three
    # company suffixes that actually appear in this file back to uppercase.
    df_organizations["NAME"] = df_organizations["NAME"].str.replace(r"\bLlc\b", "LLC", regex=True)
    df_organizations["NAME"] = df_organizations["NAME"].str.replace(r"\bInc\b", "INC", regex=True)
    df_organizations["NAME"] = df_organizations["NAME"].str.replace(r"\bPc\b", "PC", regex=True)

    # STATE is the two letter postal code, so it stays uppercase.
    df_organizations["STATE"] = df_organizations["STATE"].str.strip().str.upper()

    # Rebuild the ZIP code. Massachusetts ZIPs start with 0, which is dropped when
    # the value is stored as a number. Anything longer than 5 digits is ZIP5 and
    # ZIP4 run together, so pad it to the full 9 and keep the first 5. Shorter
    # values only need the leading zero padded back on.
    zip_digits = df_organizations["ZIP"].astype(str).str.replace(r"\D", "", regex=True)
    df_organizations["ZIP"] = zip_digits.where(
        zip_digits.str.len() <= 5, zip_digits.str.zfill(9).str[:5]
    ).str.zfill(5)

    # Reduce the phone number to its first 10 digits, which also throws away the
    # repeated copy in "978-342-9781 Or 978-342-9781", then format them uniformly.
    # Anything that does not have 10 digits is not a usable phone number.
    phone_digits = (
        df_organizations["PHONE"].astype(str).str.replace(r"\D", "", regex=True).str[:10]
    )
    df_organizations["PHONE"] = np.where(
        phone_digits.str.len() == 10,
        phone_digits.str.replace(r"^(\d{3})(\d{3})(\d{4})$", r"(\1) \2-\3", regex=True),
        np.nan,
    )

    # REVENUE is 0.0 on every row, so it tells us nothing and is dropped.
    df_organizations.drop(columns=["REVENUE"], inplace=True)

    # Coordinates must be real numbers; anything unparseable becomes NaN.
    df_organizations["LAT"] = pd.to_numeric(df_organizations["LAT"], errors="coerce")
    df_organizations["LON"] = pd.to_numeric(df_organizations["LON"], errors="coerce")

    # UTILIZATION is a visit count, so force it to a whole number.
    df_organizations["UTILIZATION"] = (
        pd.to_numeric(df_organizations["UTILIZATION"], errors="coerce").fillna(0).astype(int)
    )

    # An organization can only appear once, so keep the first row per id.
    duplicate_ids = int(df_organizations["Id"].duplicated().sum())
    df_organizations.drop_duplicates(subset=["Id"], keep="first", inplace=True)

    # A row with no name is unusable as a dimension record. The dirty batch
    # generator injects exactly this case, so the cleaner has to handle it.
    rows_before = len(df_organizations)
    df_organizations = df_organizations[
        df_organizations["NAME"].notna() & (df_organizations["NAME"].str.strip() != "")
    ]
    missing_name = rows_before - len(df_organizations)

    # Rename the columns to lowercase snake_case to match the Postgres convention.
    df_organizations.rename(
        columns={
            "Id": "id",
            "NAME": "name",
            "ADDRESS": "address",
            "CITY": "city",
            "STATE": "state",
            "ZIP": "zip",
            "PHONE": "phone",
            "LAT": "lat",
            "LON": "lon",
            "UTILIZATION": "utilization",
        },
        inplace=True,
    )

    new_col = ["id", "name", "address", "city", "state", "zip", "phone", "lat", "lon", "utilization"]
    df_organizations = df_organizations.loc[:, new_col]

    # "replace" keeps this script re-runnable: running it twice never doubles the rows.
    df_organizations.to_sql("organizations_clean", engine, if_exists="replace", index=False)

    print(f"Dropped {duplicate_ids} duplicate id(s) and {missing_name} unnamed row(s)")
    print(f"Loaded {len(df_organizations)} of {rows_read} rows into 'organizations_clean'.")

    # load_nexora.py uses these numbers for its summary and its audit table.
    return {
        "dataset": "organizations",
        "rows_read": rows_read,
        "rows_loaded": len(df_organizations),
        "rows_rejected": duplicate_ids + missing_name,
    }


if __name__ == "__main__":
    cleaning_organizations_data()
