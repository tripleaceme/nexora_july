# Day 2 — Explore the Data

🎯 **Goal:** understand what's inside the Synthea files, pick the 6 we need, and write your first data dictionary.

## What you'll learn
- How to explore unknown data before writing any code
- That deciding what **not** to use is a real engineering decision

## Your tasks

**1. Download the data** **[ADD DRIVE LINK]** and unzip it into `data/source/`. You'll see 18 CSV files. We only need 6:

| File | What it is |
|---|---|
| patients.csv | The patients |
| encounters.csv | Visits — our "appointments" |
| organizations.csv | The clinics |
| providers.csv | The doctors/clinicians |
| payers.csv | Insurance companies |
| conditions.csv | Diagnoses made during visits |

**2. Look inside each of the 6 files.** Open Python and explore:
```python
import pandas as pd
df = pd.read_csv("data/source/patients.csv", dtype=str)
print(df.shape)        # how many rows and columns?
print(df.columns)      # what columns?
df.head()              # what does the data look like?
```

**3. Find the connections.** In `encounters.csv`, look at the PATIENT, ORGANIZATION, PROVIDER, and PAYER columns — they contain IDs that point to rows in the other files. Sketch this on paper: encounters in the middle, arrows to the other tables.

**4. Hunt for the traps.** Check these yourself — they will matter later:
- What happens to a ZIP code like `02118` if you load the CSV **without** `dtype=str`? Try it.
- What do the dates look like? (Hint: `2016-01-30T22:47:14Z` — that Z means UTC time.)
- What's the earliest and latest encounter date? (You'll be surprised.)
- patients.csv has SSN and name columns. We will **not** load those — that's private health information (PHI).

**5. Write your data dictionary.** Create `docs/data_dictionary.md`. For each of the 6 files write: the columns you'll keep, what each one means, the row count, and which columns link to other files.

**6. Why not the other 12 files?** Add a short section: observations.csv is huge (114k rows) and shaped completely differently; claims files are a whole billing system. Write one sentence each — knowing why you exclude something is part of the job.

## ✅ You're done when
- [ ] `docs/data_dictionary.md` covers all 6 files
- [ ] You can say which column in encounters points to which file
- [ ] You saw the ZIP code problem with your own eyes
- [ ] You committed the data dictionary

## 💡 Tip
Quick row count without Python: `wc -l data/source/*.csv`
