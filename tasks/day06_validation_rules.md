# Day 6 — Validation, Part 1: Row Rules

🎯 **Goal:** code that checks every row against simple rules and splits data into "good rows" and "rejected rows with reasons".

## What you'll learn
- How real pipelines decide what data to trust
- Why a rejected row must carry the reason it was rejected

## Your tasks

**1. Add rules to your specs in `config.py`.** For each dataset, add things like:
```python
"required": ["id", "birthdate", "gender"],       # must not be empty
"uuid_columns": ["id"],                          # must look like a UUID
"date_columns": ["birthdate", "deathdate"],      # must parse as a date
"allowed_values": {"gender": {"M", "F"}},
```
For encounters also add: the 10 allowed encounter classes (go look at the real values with `df["ENCOUNTERCLASS"].unique()`), and the rule that STOP can't be before START.

**2. Create `etl/validate.py`** with one function: takes a dataframe + spec, returns two dataframes — `valid` and `rejected`. The trick for collecting reasons: give every row an empty list first, then let each rule append to it.
```python
df["_reasons"] = [[] for _ in range(len(df))]
# rule example: required fields
for col in spec.get("required", []):
    bad = df[col] == ""
    df.loc[bad, "_reasons"] = df.loc[bad, "_reasons"].apply(
        lambda r: r + [f"missing mandatory field: {col}"])
```
Checking "does this parse as a date?" without crashing:
```python
parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
bad = (df[col] != "") & parsed.isna()   # had a value, but it doesn't parse
```
UUID check: `uuid.UUID(value)` throws an error for bad values — wrap it in a small helper function with try/except.

**3. Important: don't stop at the first problem.** A row can be missing a field AND have a bad date. Record **all** reasons — the clinic fixing their export needs the full list.

**4. Split at the end:**
```python
failed = df["_reasons"].str.len() > 0
rejected = df[failed].copy()
rejected["rejection_reason"] = rejected["_reasons"].str.join("; ")
valid = df[~failed].drop(columns=["_reasons"])
```

**5. Test with tiny fake data.** Make a 3-row dataframe by hand: one perfect row, one with an empty required field, one with a garbage date. Run validation. Did each row land where it should, with the right reason?

## ✅ You're done when
- [ ] Validation returns valid + rejected with a readable `rejection_reason`
- [ ] A row with two problems shows **both** reasons
- [ ] The real 6 files all pass (Synthea data is clean — Day 12 will fix that 😉)
- [ ] Committed

## 💡 Tip
Print the reasons as you go: `print(rejected["rejection_reason"].tolist())`. Readable reasons now = easy debugging later.
