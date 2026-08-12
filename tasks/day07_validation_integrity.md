# Day 7 — Validation, Part 2: Duplicates, Broken Links & Quarantine

🎯 **Goal:** catch duplicate rows and rows that point at things that don't exist — and save every rejected row to a quarantine folder.

## What you'll learn
- Referential integrity: no appointment should point at a patient that doesn't exist
- Why processing order matters (parents before children)

## Your tasks

**1. Duplicates.** Add a duplicate check to `validate.py`: if the same id appears twice, keep the first, reject the rest.
```python
dup = df.duplicated(subset=["id"], keep="first")
```
(For conditions there's no id — use the combination patient + encounter + code + start date.)

**2. Broken links (the big one).** An encounter has a `patient_id`. That patient must exist — either in this batch's valid patients, or already in the database from an earlier week. So:
- Process datasets in **this order**: organizations → payers → providers → patients → encounters → conditions. Parents first, children after.
- After validating each dataset, remember its set of valid ids.
- Also fetch the ids already in the database:
```python
cur.execute("SELECT id FROM patients")
db_ids = {str(row[0]) for row in cur.fetchall()}
known_patients = valid_batch_ids | db_ids
```
- When validating encounters, reject any row whose `patient_id` is not in `known_patients`. Same for organization, provider, payer. Same idea again for conditions (which point at patients AND encounters).

**3. Notice the chain reaction.** If a patient is rejected on Day 6 rules, their encounters now get rejected too ("unknown reference: patient_id"), and those encounters' conditions as well. That's not a bug — that's the design. Nothing half-connected ever reaches the database.

**4. Quarantine.** Rejected rows must not vanish. Write them to:
```
data/rejected/<run_id>/patients_rejected.csv
```
with the `rejection_reason` column included. The `run_id` can be a timestamp like `20260718T093000` — you'll generate one per pipeline run.

**5. Test the chain.** Take a small copy of the data, break one patient on purpose (blank their birthdate), and confirm: patient rejected → their encounters rejected → those conditions rejected.

## ✅ You're done when
- [ ] Duplicates are caught (keep first, reject the rest)
- [ ] An encounter pointing at a fake patient id gets rejected
- [ ] The chain reaction works and you watched it happen
- [ ] Rejected CSVs appear in `data/rejected/<run_id>/`
- [ ] Committed

## 💡 Tip
Python sets make the link check fast and easy: build a `set()` of known ids, then `df["patient_id"].isin(known)` does the rest.
