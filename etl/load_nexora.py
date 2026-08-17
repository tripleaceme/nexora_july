"""Run the whole Nexora CareSync ETL: clean all six extracts, load Postgres.

If one dataset fails, the rest still run. The failure is printed, saved to
etl_run_log as "failed", and the script exits with code 1 so you notice. To
retry only that dataset afterwards, run its own cleaner instead of this file,
for example: python etl/clean_patients.py

Usage:
    python etl/load_nexora.py
"""

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

project_root = Path(__file__).resolve().parents[1]
load_dotenv(project_root / ".env")

# Let Python find the six cleaning scripts, which sit next to this file.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# from file_name import function_name
from clean_conditions import cleaning_conditions_data      
from clean_encounters import cleaning_encounters_data      
from clean_organizations import cleaning_organizations_data
from clean_patients import cleaning_patients_data          
from clean_payers import cleaning_payers_data              
from clean_providers import cleaning_providers_data        

# Name saved against this run in etl_run_log. Change it to something like
# "week_01" when you load a weekly batch, so the runs are easy to tell apart.
RUN_LABEL = "full_load"

# The order matters, so this list is not alphabetical. encounters holds foreign
# keys to all four dimensions above it, and conditions holds one to encounters.
PIPELINE = [
    ("organizations", cleaning_organizations_data),
    ("providers", cleaning_providers_data),
    ("payers", cleaning_payers_data),
    ("patients", cleaning_patients_data),
    ("encounters", cleaning_encounters_data),
    ("conditions", cleaning_conditions_data),
]


run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

# One connection, shared by all six cleaners.
engine = create_engine(os.getenv("DATABASE_URL"))

print("=" * 70)
print(f"Nexora CareSync ETL  |  run_id={run_id}  |  label={RUN_LABEL}")
print(f"Reading from: {os.getenv('DATA_DIR', 'data/source')}")
print(f"Datasets:     {', '.join(name for name, _ in PIPELINE)}")
print("=" * 70)
cleaning_organizations_data()
print("=" * 70)
cleaning_providers_data()
print("=" * 70)
cleaning_patients_data()
print("=" * 70)
cleaning_payers_data()
print("=" * 70)
cleaning_conditions_data()
print("=" * 70)
cleaning_encounters_data()