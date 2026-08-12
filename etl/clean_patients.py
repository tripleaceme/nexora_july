import pandas as pd
from pathlib import Path
import numpy as np
import psycopg2
from sqlalchemy import create_engine
conn = psycopg2.connect(
    host="localhost",
    database="nexora_health",
    user="nexora",
    password="nexora_dev"
)

engine = create_engine('postgresql+psycopg2://nexora:nexora_dev@localhost/nexora_health')


print("Starting the ETL process for cleaning patients data...")

root_path = Path("/Users/mac/Documents/Amdari/Amdari/Nexora_Health/nexora-caresync-pipeline/data/source")

# Read the patients data from the CSV file into a DataFrame called df_patients.
df_patients = pd.read_csv(root_path / "patients.csv")

# Read the missing FIPS codes from the CSV file into a DataFrame called fill_fips.
fill_fips = pd.read_csv(root_path / "missing_fips.csv")

# Trim the ID column to retain only the last elements when splitted by -
df_patients["Id"] = df_patients["Id"].str.split("-").str[-1]


# Convert the "BIRTHDATE" column to datetime format, handling errors by coercing invalid formats to NaT (Not a Time).
df_patients["BIRTHDATE"] = pd.to_datetime(df_patients["BIRTHDATE"], errors='coerce')

# convert deathdate to datetime format, handling errors by coercing invalid formats to NaT (Not a Time).
df_patients["DEATHDATE"] = pd.to_datetime(df_patients["DEATHDATE"], errors='coerce')

# drop ssn, drivers, passpor and prefix columns from the dataframe as they are not needed for further analysis.
df_patients.drop(columns=["SSN", "DRIVERS", "PASSPORT", "PREFIX"], inplace=True)


# fill missing values in marital with unknown as it is a categorical variable and we don't want to lose any data.
df_patients["MARITAL"].fillna("Unknown", inplace=True)

# strip off the numbers in the first, middle and last name columns to retain only the alphabetic characters.
df_patients["FIRST"] = df_patients["FIRST"].str.replace(r'\d+', '', regex=True)
df_patients["LAST"] = df_patients["LAST"].str.replace(r'\d+', '', regex=True)


# combine first, middle and last name columns into a single column called "FULL_NAME"
df_patients["FULL_NAME"] = df_patients[["FIRST", "MIDDLE", "LAST"]].apply(lambda x: ' '.join(x.dropna()), axis=1)

# drop first, middle and last name columns as they are no longer needed after creating the FULL_NAME column.
# drop suffix and maiden name columns as they are not needed for further analysis.
df_patients.drop(columns=["FIRST", "MIDDLE", "LAST", "SUFFIX", "MAIDEN"], inplace=True)


# Replace all missing values of Marital status with unknown as it is a categorical variable and we don't want to lose any data.
df_patients["MARITAL"] = df_patients["MARITAL"].map({"M": "Married", "S": "Single",
                                                            "D": "Divorced", "W": "Widowed","Unknown": "Unknown"})

# Standardize the "RACE", "ETHNICITY" columns by converting all values to title case (first letter capitalized) for consistency.
df_patients["RACE"] = df_patients["RACE"].str.title()
df_patients["ETHNICITY"] = df_patients["ETHNICITY"].str.title()

# Map the "GENDER" column values from "M" and "F" to "Male" and "Female" respectively for clarity and consistency
df_patients["GENDER"] = df_patients["GENDER"].map({"M": "Male", "F": "Female"})


# update the birthplace for patient with the Id c93095b90340 to Shanghai  
# Shanghai-Municipality  CN so as to have a consistent format for all the birthplace values.
df_patients.loc[df_patients["Id"] == "c93095b90340", "BIRTHPLACE"] = "Shanghai  Shanghai-Municipality  CN" 


# split the "BIRTHPLACE" column into three separate columns: "BIRTHPLACE_CITY", "BIRTHPLACE_STATE", and 
# "BIRTHPLACE_COUNTRY" by splitting the string on spaces and extracting the respective parts.
df_patients["BIRTHPLACE_CITY"] = df_patients["BIRTHPLACE"].str.split(" ").str[0]
df_patients["BIRTHPLACE_STATE"] = df_patients["BIRTHPLACE"].str.split(" ").str[2]
df_patients["BIRTHPLACE_COUNTRY"] = df_patients["BIRTHPLACE"].str.split(" ").str[4]


# drop birthplace column as it is no longer needed after creating the BIRTHPLACE_CITY, 
# BIRTHPLACE_STATE and BIRTHPLACE_COUNTRY columns.
df_patients.drop(columns=["BIRTHPLACE"], inplace=True)

# Rename resident to the city, state and country columns name to have a consistent format for all the birthplace values.
df_patients.rename(columns={"CITY": "RESIDENT_CITY", 
                               "STATE": "RESIDENT_STATE", 
                               "COUNTY": "RESIDENT_COUNTY"}, inplace=True)


# Convert the "FIPS" column to string type to ensure consistency in data type for further analysis.
df_patients['FIPS'] = df_patients['FIPS'].astype(str)


# Merge the df_patients DataFrame with the fill_fips DataFrame on the "RESIDENT_COUNTY" column from df_patients and the "county" column from fill_fips.
df_patients = df_patients.merge(
    fill_fips,
    how='left',
    left_on='RESIDENT_COUNTY',
    right_on='county'
)


# drop county column as it is no longer needed after merging with the fill_fips dataframe.
df_patients.drop(columns=["county"], inplace=True)


# drop the .0 from the FIPS column values to ensure consistency in the format of the FIPS codes.
df_patients["FIPS"] = df_patients["FIPS"].str.replace(r'\.0$', '', regex=True)

# replace the string "nan" in the "FIPS" column with actual NaN values to ensure proper handling of missing data.
df_patients["FIPS"].replace("nan", np.nan, inplace=True)


# Replcae the missing values in the "FIPS" column with the corresponding values from the "fips_code" column obtained from the fill_fips DataFrame.
df_patients["FIPS"].fillna(df_patients["fips_code"], inplace=True)


# drop fips_code column as it is no longer needed after filling the missing values in the "FIPS" column.
df_patients.drop(columns=["fips_code"], inplace=True)


new_col = [
    "Id", "BIRTHDATE", "DEATHDATE", "FULL_NAME", "MARITAL", "RACE",
    "ETHNICITY", "GENDER", "ADDRESS", "RESIDENT_CITY", "RESIDENT_STATE", "RESIDENT_COUNTY",
    "BIRTHPLACE_CITY", "BIRTHPLACE_STATE", "BIRTHPLACE_COUNTRY", "FIPS", "ZIP", "LAT",
    "LON", "HEALTHCARE_EXPENSES", "HEALTHCARE_COVERAGE", "INCOME"
]


# rename the columns of the df_patients DataFrame to lowercase for a consistent format for all the column names.
df_patients.columns = df_patients.columns.str.lower()

# load the cleaned patients data into the "patients" table in the PostgreSQL database using the SQLAlchemy engine.

df_patients.to_sql('patients', engine, if_exists='append', index=False)

print("Data inserted successfully into the 'patients' table.")