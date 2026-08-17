"""

Clean the raw patients.csv extract and load it into Postgres.

patients is the main dimension of the star schema: one row per person that
encounters and conditions are recorded against.


Run on its own:
    python etl/clean_patients.py

Or run all six cleaners at once:
    python etl/load_nexora.py

===========================================================================================================================
    Name            |      Date          |             Version        |      Ticket        |     Requester      |   Dept
    Ayoade Adegbite |  08/17/2026        |            1.0             |     DEV-405        |    Priya Dubey     | Marketing


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


def cleaning_patients_data(source_dir=SOURCE_DIR, engine=None):
    """Clean patients.csv and load it into the patients_clean table."""
    if engine is None:
        engine = create_engine(os.getenv("DATABASE_URL"))

    print("Starting the ETL process for cleaning patients data...")

    # Read ZIP as text so pandas cannot strip the leading Massachusetts zero.
    df_patients = pd.read_csv(source_dir / "patients.csv", dtype={"ZIP": str})
    rows_read = len(df_patients)
    print(f"Read {rows_read} rows from patients.csv")

    # The county to FIPS lookup used to fill the gaps in the FIPS column.
    fill_fips = pd.read_csv(source_dir / "missing_fips.csv")

    # Trim the id down to the last part of the UUID:
    # "fe621c76-a591-b7be-5668-b77f00240d82" becomes "b77f00240d82", which is
    # much easier to read. encounters.PATIENT and conditions.PATIENT are
    # trimmed the same way, so those links still match.
    df_patients["Id"] = df_patients["Id"].str.strip().str.lower().str.split("-").str[-1]

    # Convert the date columns to real dates. errors="coerce" turns an
    # unreadable value into NaT instead of crashing the whole run.
    df_patients["BIRTHDATE"] = pd.to_datetime(df_patients["BIRTHDATE"], errors="coerce")
    df_patients["DEATHDATE"] = pd.to_datetime(df_patients["DEATHDATE"], errors="coerce")

    # SSN, DRIVERS and PASSPORT identify a real person on their own, and PREFIX
    # adds nothing to the analysis, so none of them reach the warehouse.
    df_patients.drop(columns=["SSN", "DRIVERS", "PASSPORT", "PREFIX"], inplace=True)

    # Strip Synthea's synthetic digits out of all three name parts. MIDDLE needs
    # this as much as FIRST and LAST do, otherwise the assembled full name comes
    # out as "Malvina Leonia336 Rohan".
    for col in ["FIRST", "MIDDLE", "LAST"]:
        df_patients[col] = df_patients[col].str.replace(r"\d+", "", regex=True)

    # Combine the three name parts into one column. dropna() inside the join is
    # what lets a patient with no middle name through without a double space.
    df_patients["FULL_NAME"] = (
        df_patients[["FIRST", "LAST"]]
        .apply(lambda parts: " ".join(parts.dropna()), axis=1)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    # The name parts are now redundant, and SUFFIX and MAIDEN are not analysed.
    df_patients.drop(columns=["FIRST", "MIDDLE", "LAST", "SUFFIX", "MAIDEN"], inplace=True)

    # A blank marital status is not an error, so it becomes an explicit
    # "Unknown" category rather than a null. Assign the result back instead of
    # using inplace=True on a column: that style is deprecated in pandas 2 and
    # stops working in pandas 3.
    df_patients["MARITAL"] = df_patients["MARITAL"].fillna("Unknown")
    df_patients["MARITAL"] = df_patients["MARITAL"].map(
        {"M": "Married", "S": "Single", "D": "Divorced", "W": "Widowed", "Unknown": "Unknown"}
    )

    # Standardise the demographic categories to title case for consistency.
    df_patients["RACE"] = df_patients["RACE"].str.title()
    df_patients["ETHNICITY"] = df_patients["ETHNICITY"].str.title()
    df_patients["GENDER"] = df_patients["GENDER"].str.strip().str.upper()
    df_patients["GENDER"] = df_patients["GENDER"].map({"M": "Male", "F": "Female"})

    # BIRTHPLACE packs three fields into one string, separated by DOUBLE spaces.
    # Splitting on a double space rather than a single one is what keeps
    # "Shanghai  Shanghai Municipality  CN" intact: splitting on every space
    # would cut the state down to "Municipality".
    birthplace = df_patients["BIRTHPLACE"].str.split(r"\s{2,}", regex=True, expand=True)
    df_patients["BIRTHPLACE_CITY"] = birthplace[0].str.strip()
    df_patients["BIRTHPLACE_STATE"] = birthplace[1].str.strip()
    df_patients["BIRTHPLACE_COUNTRY"] = birthplace[2].str.strip()
    df_patients.drop(columns=["BIRTHPLACE"], inplace=True)

    # There are now two sets of place columns, so label the ones that describe
    # where the patient lives today.
    df_patients.rename(
        columns={
            "CITY": "RESIDENT_CITY",
            "STATE": "RESIDENT_STATE",
            "COUNTY": "RESIDENT_COUNTY",
        },
        inplace=True,
    )

    # FIPS is a county code, not a measurement, so it belongs in a text column.
    # Reading it as a number first leaves "25017.0" behind, hence the trailing
    # ".0" strip, and the literal text "nan" has to become a real null before
    # fillna() can see it as missing.
    df_patients["FIPS"] = (
        df_patients["FIPS"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    )
    df_patients["FIPS"] = df_patients["FIPS"].replace({"nan": np.nan, "": np.nan, "None": np.nan})

    # The lookup file has a space in front of every code and stores it as a
    # number. Strip and convert both sides so the merge key and the filled
    # value are the same type as the column they land in.
    fill_fips["county"] = fill_fips["county"].astype(str).str.strip()
    fill_fips["fips_code"] = fill_fips["fips_code"].astype(str).str.strip()
    df_patients["RESIDENT_COUNTY"] = df_patients["RESIDENT_COUNTY"].str.strip()

    df_patients = df_patients.merge(
        fill_fips, how="left", left_on="RESIDENT_COUNTY", right_on="county"
    )
    df_patients["FIPS"] = df_patients["FIPS"].fillna(df_patients["fips_code"])
    df_patients.drop(columns=["county", "fips_code"], inplace=True)

    # Rebuild the ZIP the same way organizations and providers do, so a
    # Massachusetts ZIP keeps the leading zero it was written without.
    zip_digits = df_patients["ZIP"].astype(str).str.replace(r"\D", "", regex=True)
    df_patients["ZIP"] = (
        zip_digits.where(zip_digits.str.len() <= 5, zip_digits.str.zfill(9).str[:5])
        .str.zfill(5)
        .replace({"00000": np.nan})
    )

    # Coordinates and money columns must be numbers. A stray "N/A" in a future
    # weekly batch becomes NaN here instead of turning the column into text.
    for col in ["LAT", "LON"]:
        df_patients[col] = pd.to_numeric(df_patients[col], errors="coerce")
    for col in ["HEALTHCARE_EXPENSES", "HEALTHCARE_COVERAGE", "INCOME"]:
        df_patients[col] = pd.to_numeric(df_patients[col], errors="coerce").round(2)

    # A patient can only appear once, so keep the first row per id.
    duplicate_ids = int(df_patients["Id"].duplicated().sum())
    df_patients.drop_duplicates(subset=["Id"], keep="first", inplace=True)

    # A row with no id cannot be pointed at by an encounter, so it is useless
    # as a dimension record.
    rows_before = len(df_patients)
    df_patients = df_patients[df_patients["Id"].notna() & (df_patients["Id"].str.strip() != "")]
    missing_id = rows_before - len(df_patients)

    # Rename the columns to lowercase snake_case to match the Postgres convention.
    df_patients.columns = df_patients.columns.str.lower()

    new_col = [
        "id", "birthdate", "deathdate", "full_name", "marital", "race",
        "ethnicity", "gender", "address", "resident_city", "resident_state", "resident_county",
        "birthplace_city", "birthplace_state", "birthplace_country", "fips", "zip", "lat",
        "lon", "healthcare_expenses", "healthcare_coverage", "income",
    ]
    df_patients = df_patients.loc[:, new_col]

    # "replace" keeps this script re-runnable. The earlier version appended to
    # a table called "patients", which is why that table ended up holding 113
    # rows for an 87 row file: every rerun stacked another copy on top.
    df_patients.to_sql("patients_clean", engine, if_exists="replace", index=False)

    print(f"Dropped {duplicate_ids} duplicate id(s) and {missing_id} row(s) with no id")
    print(f"Loaded {len(df_patients)} of {rows_read} rows into 'patients_clean'.")

    # load_nexora.py uses these numbers for its summary and its audit table.
    return {
        "dataset": "patients",
        "rows_read": rows_read,
        "rows_loaded": len(df_patients),
        "rows_rejected": duplicate_ids + missing_id,
    }


if __name__ == "__main__":
    cleaning_patients_data()
