# Day 4 — Build the Extract Step

🎯 **Goal:** Python code that reads the CSVs safely, keeps only the columns we need, and drops private data before it goes anywhere.

## What you'll learn
- Why we read everything as text first
- PHI minimization: the safest private data is data you never load

## Your tasks

**1. Create your package layout:**
```
etl/
  __init__.py
  config.py
  extract.py
```

**2. In `config.py`, describe each dataset once.** A simple dictionary per dataset works great:
```python
DATASETS = {
    "patients": {
        "file": "patients.csv",
        "columns": {          # CSV column -> our column name
            "Id": "id",
            "BIRTHDATE": "birthdate",
            "GENDER": "gender",
            "CITY": "city",
            # ... the columns you chose in your data dictionary
        },
    },
    # ... same idea for the other 5 datasets
}
```
Notice what's **missing** from patients: SSN, names, passport. We never even read them. That's PHI minimization — done at the earliest possible moment.

**3. In `extract.py`, write one function** that works for any dataset:
```python
import pandas as pd

def extract(source_dir, spec):
    df = pd.read_csv(f"{source_dir}/{spec['file']}", dtype=str, keep_default_na=False)
    # 1. fail with a clear message if any expected column is missing
    # 2. keep only the columns in spec["columns"], rename them
    # 3. strip whitespace from every value
    return df
```
Why `dtype=str`? Remember the ZIP code from Day 2 — `02118` must stay `02118`. We convert types later, on purpose, not by accident.

**4. Fail loudly.** If the file doesn't exist, or a column is missing, raise an error with a message a human can act on ("patients.csv: missing column BIRTHDATE"). A half-broken weekly export should stop the pipeline, not sneak through.

**5. Test it in a Python shell:**
```python
from etl.config import DATASETS
from etl.extract import extract
df = extract("data/source", DATASETS["patients"])
print(df.shape, list(df.columns))
```

## ✅ You're done when
- [ ] `extract()` works for all 6 datasets
- [ ] The patients result has NO ssn or name columns
- [ ] Renaming a column in a copy of the CSV makes it fail with a clear error
- [ ] Committed

## 💡 Tip
One generic function + one spec dictionary beats six copy-pasted functions. When something changes, you fix it in one place.
