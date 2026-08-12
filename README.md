# Nexora CareSync — Weekly Patient & Appointment Ingestion Pipeline

Ingests weekly patient and appointment (encounter) exports from Nexora Health's
partner clinics into a local PostgreSQL reporting database. One cleaning script
per dataset: read the raw CSV, fix the defects that dataset actually has, drop
the rows that can't be loaded, and write the result to Postgres.

All data is **synthetic**, generated with [Synthea](https://synthetichealth.github.io/synthea/).
The build is worked through day by day in [tasks/](tasks/).

## Data

Six source files in [data/source/](data/source/), plus a small lookup:

| File | Rows | Role |
|---|---:|---|
| `organizations.csv` | 283 | dimension — clinics and hospitals |
| `providers.csv` | 283 | dimension — clinicians, each in one organization |
| `payers.csv` | 10 | dimension — insurers |
| `patients.csv` | 87 | dimension — patients |
| `encounters.csv` | 7,210 | **fact** — one row per appointment |
| `conditions.csv` | 4,748 | detail — diagnoses recorded at a visit |
| `missing_fips.csv` | 8 | lookup — county → FIPS, fills gaps in `patients` |

`encounters` is the centre of the star: it points at a patient, an
organization, a provider and a payer. `conditions` hangs off `encounters`.

## Setup

Requires Python 3.10+ and PostgreSQL 14+ running locally.

```bash
pip install -r requirements.txt

# Create the role and database
createuser nexora --pwprompt
createdb nexora_health -O nexora

# Configure credentials
cp .env.example .env   # then edit DB_PASSWORD
```

The cleaners create their own tables via pandas `to_sql`, so there is no DDL
step to run.

## Running the cleaners

Run in dependency order — dimensions before the fact table that references them:

```bash
python etl/clean_organizations.py
python etl/clean_providers.py
python etl/clean_payers.py
python etl/clean_patients.py
python etl/clean_encounters.py
python etl/clean_conditions.py
```

`DATA_DIR` in `.env` selects which batch to read, so the same scripts run
against `data/source` or any `data/incoming/week_*` folder without edits.

Each script prints how many rows it read, how many it dropped and why, and how
many it loaded. Five of the six also write a cleaned CSV to `data/clean/` so the
result can be inspected without opening the database.

## What each cleaner does

**`clean_organizations.py`** → `organizations_clean`
Rebuilds ZIP codes (Massachusetts leading zeros were lost to a numeric read; 274
rows are ZIP5+ZIP4 run together). Title-cases shouted names and addresses, then
restores `LLC`/`INC`/`PC`. Reduces phones to their first 10 digits, which also
discards the one row holding the same number twice. Drops `REVENUE` (0.0 on
every row) and unnamed rows.

**`clean_providers.py`** → `providers_clean`
Strips Synthea's synthetic digits from names (`Gabriel934 Reilly981` →
`Gabriel Reilly`). Same ZIP repair as organizations. Keeps `gender` as the M/F
code and adds a readable `gender_label` alongside it. Drops `PROCEDURES` (0 on
every row) and rows with no name or no parent organization.

**`clean_payers.py`** → `payers_clean`
Drops five columns that are empty on all 10 rows. Converts the `NO_INSURANCE`
token to `No Insurance`. Deliberately does *not* title-case `NAME`, which would
turn `UnitedHealthcare` into `Unitedhealthcare`. Derives `coverage_rate`,
guarding against a zero denominator.

**`clean_patients.py`** → `patients`
Trims the UUID to its last segment. Drops SSN, driver's licence, passport and
prefix. Combines the name parts into `full_name` and splits `BIRTHPLACE` into
city/state/country. Fills missing FIPS codes from `missing_fips.csv`.

**`clean_encounters.py`** → `encounters_clean`
Parses `START`/`STOP` as UTC — they end in `Z`, and storing an appointment time
without its zone is how reports end up an hour out. Derives `duration_minutes`,
`uncovered_amount` and `coverage_rate`. Reads `CODE`/`REASONCODE` as text so a
clinical code never prints as `10509002.0` (`REASONCODE` is blank on 2,949 rows,
which is what forced the column to float). Splits the trailing qualifier off
`DESCRIPTION` into `description_type`. Lowercases but does not title-case
`ENCOUNTERCLASS`, which is a controlled vocabulary. Rejects rows that stop
before they start, carry an encounter class outside the allowed list, or are
missing a dimension key.

**`clean_conditions.py`** → `conditions_clean`
Has no id column, so a row is identified by `PATIENT + ENCOUNTER + CODE + START`
and de-duplicated on that key. An empty `STOP` is not missing data — it means
the condition is still open, so it stays null and gets an `is_ongoing` flag,
with `duration_days` left null. Splits the bracketed clinical qualifier out of
`DESCRIPTION` into `condition_category`.

## PHI minimization

Direct identifiers in the raw export — SSN, driver's licence, passport number —
are dropped during cleaning and never reach the database.

## Repository layout

```
├── data/
│   ├── source/          # Synthea export (committed, synthetic data)
│   └── clean/           # cleaned CSVs written by the cleaners (generated)
├── etl/
│   ├── clean_organizations.py
│   ├── clean_providers.py
│   ├── clean_payers.py
│   ├── clean_patients.py
│   ├── clean_encounters.py
│   ├── clean_conditions.py
│   ├── ETL copy.ipynb        # exploration scratchpad across all six files
│   └── ETL patients.ipynb    # working notebook clean_patients.py came from
└── tasks/               # the 15-day build brief, one file per day
```