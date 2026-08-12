"""Clean the raw providers.csv extract and load it into Postgres.

providers is a dimension of the star schema: one row per clinician an
encounter can be attributed to. Every provider belongs to one organization.

Issues found in the raw extract (283 rows):
  - NAME carries Synthea's synthetic digits ("Gabriel934 Reilly981").
  - ZIP has the same lost-leading-zero corruption as organizations.csv.
  - ADDRESS and CITY are uppercase and contain double spaces.
  - SPECIALITY is "GENERAL PRACTICE" on every row.
  - PROCEDURES is 0 on every row, so it carries no information.

Note on GENDER: the star schema providers table has a
CHECK (gender IN ('M','F')) constraint, so the single letter code is kept in
gender and the readable label is added next to it as gender_label. This is
deliberately different from clean_patients.py, which replaces the code
outright. Doing that here would violate the constraint.

Run:
    python etl/clean_providers.py
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Read the database settings from .env instead of hard-coding the password.
project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")

# DATA_DIR in .env selects which batch to clean, so the same script can run
# against data/source or any data/incoming/week_* folder.
source_dir = project_root / os.getenv("DATA_DIR", "data/source")
clean_dir = project_root / "data" / "clean"
clean_dir.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER', 'nexora')}:"
    f"{os.getenv('DB_PASSWORD', 'nexora_dev')}@"
    f"{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/"
    f"{os.getenv('DB_NAME', 'nexora_health')}"
)

print("Starting the ETL process for cleaning providers data...")

# Read ZIP as text so pandas cannot strip the leading zero a second time.
df_providers = pd.read_csv(source_dir / "providers.csv", dtype={"ZIP": str})
rows_read = len(df_providers)
print(f"Read {rows_read} rows from providers.csv")


# Keep the full UUIDs. providers.Id is referenced by encounters.PROVIDER, and
# ORGANIZATION points back at organizations.Id, so neither can be trimmed.
df_providers["Id"] = df_providers["Id"].str.strip().str.lower()
df_providers["ORGANIZATION"] = df_providers["ORGANIZATION"].str.strip().str.lower()


# Strip Synthea's synthetic digits out of the name, the same way
# clean_patients.py does: "Gabriel934 Reilly981" becomes "Gabriel Reilly".
df_providers["NAME"] = df_providers["NAME"].str.replace(r"\d+", "", regex=True)
df_providers["NAME"] = (
    df_providers["NAME"].str.replace(r"\s+", " ", regex=True).str.strip().str.title()
)


# GENDER stays as the M/F code so the star schema CHECK constraint still
# passes, and the readable label goes into its own column for reporting.
df_providers["GENDER"] = df_providers["GENDER"].str.strip().str.upper()
df_providers["GENDER_LABEL"] = df_providers["GENDER"].map({"M": "Male", "F": "Female"})


# SPECIALITY is uppercase on every row, so title case it for display.
df_providers["SPECIALITY"] = (
    df_providers["SPECIALITY"].str.replace(r"\s+", " ", regex=True).str.strip().str.title()
)


# Standardise the location columns the same way as organizations.
df_providers["ADDRESS"] = (
    df_providers["ADDRESS"].str.replace(r"\s+", " ", regex=True).str.strip().str.title()
)
df_providers["CITY"] = (
    df_providers["CITY"].str.replace(r"\s+", " ", regex=True).str.strip().str.title()
)
df_providers["STATE"] = df_providers["STATE"].str.strip().str.upper()


# Rebuild the ZIP code. Massachusetts ZIPs start with 0, which is dropped when
# the value is stored as a number. Anything longer than 5 digits is ZIP5 and
# ZIP4 run together, so pad it to the full 9 and keep the first 5.
zip_digits = df_providers["ZIP"].astype(str).str.replace(r"\D", "", regex=True)
df_providers["ZIP"] = zip_digits.where(
    zip_digits.str.len() <= 5, zip_digits.str.zfill(9).str[:5]
).str.zfill(5)


# Coordinates must be real numbers; anything unparseable becomes NaN.
df_providers["LAT"] = pd.to_numeric(df_providers["LAT"], errors="coerce")
df_providers["LON"] = pd.to_numeric(df_providers["LON"], errors="coerce")


# ENCOUNTERS is a workload count, so force it to a whole number.
df_providers["ENCOUNTERS"] = (
    pd.to_numeric(df_providers["ENCOUNTERS"], errors="coerce").fillna(0).astype(int)
)


# PROCEDURES is 0 on every row, so it tells us nothing and is dropped.
df_providers.drop(columns=["PROCEDURES"], inplace=True)


# A provider can only appear once, so keep the first row per id.
duplicate_ids = df_providers["Id"].duplicated().sum()
df_providers.drop_duplicates(subset=["Id"], keep="first", inplace=True)


# A provider with no name, or with no parent organization to hang off, cannot
# be used as a dimension record.
rows_before = len(df_providers)
df_providers = df_providers[
    df_providers["NAME"].notna()
    & (df_providers["NAME"].str.strip() != "")
    & df_providers["ORGANIZATION"].notna()
]
dropped_incomplete = rows_before - len(df_providers)


# Rename the columns to lowercase snake_case to match the Postgres convention.
df_providers.rename(
    columns={
        "Id": "id",
        "ORGANIZATION": "organization_id",
        "NAME": "full_name",
        "GENDER": "gender",
        "GENDER_LABEL": "gender_label",
        "SPECIALITY": "speciality",
        "ADDRESS": "address",
        "CITY": "city",
        "STATE": "state",
        "ZIP": "zip",
        "LAT": "lat",
        "LON": "lon",
        "ENCOUNTERS": "encounters",
    },
    inplace=True,
)

new_col = [
    "id", "organization_id", "full_name", "gender", "gender_label", "speciality",
    "address", "city", "state", "zip", "lat", "lon", "encounters",
]
df_providers = df_providers.loc[:, new_col]


# Save a copy of the cleaned file so the result can be inspected without the database.
df_providers.to_csv(clean_dir / "providers.csv", index=False)

# "replace" keeps this script re-runnable: running it twice never doubles the rows.
df_providers.to_sql("providers_clean", engine, if_exists="replace", index=False)

print(f"Dropped {duplicate_ids} duplicate id(s) and {dropped_incomplete} incomplete row(s)")
print(f"Loaded {len(df_providers)} of {rows_read} rows into 'providers_clean'.")
