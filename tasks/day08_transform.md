# Day 8 — Build the Transform Step

🎯 **Goal:** turn validated text data into properly typed data, ready for the database.

## What you'll learn
- Why transform comes AFTER validation (and why that makes it simple)
- How empty strings become real NULLs in the database

## Your tasks

**1. Create `etl/transform.py`** with one function: takes the **valid** dataframe + spec, returns a typed dataframe. It does only four things:

```python
# 1. dates -> real dates
df[col] = pd.to_datetime(df[col], format="mixed").dt.date

# 2. timestamps -> real timestamps, in UTC
df[col] = pd.to_datetime(df[col], utc=True, format="mixed")

# 3. money -> numbers, rounded to 2 decimals
df[col] = pd.to_numeric(df[col]).round(2)

# 4. empty strings -> None (becomes NULL in the database)
df = df.replace({"": None})
```

**2. Standardize the small stuff.** Make `gender` uppercase and `encounter_class` lowercase — so "Ambulatory" and "ambulatory" can never become two different groups in a report.

**3. Stop and appreciate something.** Yesterday's validation already proved every date parses and every number is a number. So today's code **cannot fail because of bad data** — it's short and boring, and that's exactly right. Boring is good in pipelines.

**4. One rule: no fixing here.** Found data that "needs a little cleanup"? Wrong place. That belongs in validation as a rule with a recorded reason. Transform only converts what's already proven good.

**5. Test the NULL behavior.** Take a patient with an empty `deathdate` and confirm the value is `None` after transform (not an empty string, not the text "NaT"):
```python
row = df.iloc[0]
print(repr(row["deathdate"]))   # want: None
```

## ✅ You're done when
- [ ] Dates, timestamps, and costs come out properly typed
- [ ] Empty optional fields are `None`
- [ ] gender/encounter_class have consistent casing
- [ ] Committed

## 💡 Tip
This file being small is a sign you designed the pipeline well — the hard thinking happened in validation, where problems get *recorded*, not silently patched.
