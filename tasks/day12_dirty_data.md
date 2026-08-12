# Day 12 — The Dirty Data Drill

🎯 **Goal:** the Synthea data is too clean to test your validator — so break a copy on purpose and prove every single defect gets caught.

## What you'll learn
- How engineers test data quality: plant known bugs, verify known catches
- Reading a validation report under fire

## Your tasks

**1. Write `scripts/inject_dirty_batch.py`.** It copies one weekly batch folder to `week_..._dirty/` and plants these defects (add each one as a new row or an edit — give injected rows made-up ids so you recognize them):

| # | Defect | Which rule should catch it |
|---|---|---|
| 1 | Duplicate a patient row | duplicate primary key |
| 2 | Patient with empty BIRTHDATE | missing mandatory field |
| 3 | Duplicate an encounter row | duplicate primary key |
| 4 | Encounter whose PATIENT id doesn't exist anywhere | unknown reference |
| 5 | Encounter with id "not-a-valid-uuid" | invalid UUID |
| 6 | Encounter with class "telehealth" (not in the allowed 10) | value not allowed |
| 7 | Encounter with START and STOP swapped | chronology error |
| 8 | Encounter with TOTAL_CLAIM_COST = "N/A" | non-numeric value |
| 9 | Organization with empty NAME | missing mandatory field |

Pandas makes this easy: copy a real row with `.copy()`, change one field, `pd.concat` it back, save the CSV.

**2. Run the pipeline on the dirty batch:**
```bash
python scripts/inject_dirty_batch.py data/incoming/week_2026-06-08
python -m etl.pipeline --source data/incoming/week_2026-06-08_dirty
```

**3. Score it.** Open the validation report and check off all 9: each defect caught, and — this matters — caught for the **right reason**. A bad UUID caught as "missing field" would mean a rule is misfiring.

**4. Check the collateral.** The clean rows in that batch should still have loaded normally. Catching bad rows must never block good ones.

**5. Look in quarantine.** Open `data/rejected/<run_id>/encounters_rejected.csv` — your injected rows are all there, each with its reason. This file is what you'd send back to a clinic.

**6. Save your evidence.** This validation report is a required final deliverable — commit it.

## ✅ You're done when
- [ ] 9 out of 9 defects caught, each with the correct reason
- [ ] Clean rows in the same batch still loaded
- [ ] The dirty-run validation report is committed
- [ ] The injector script is committed

## 💡 Tip
If a defect slipped through, don't patch the data — fix the rule in `validate.py`, re-run, and re-check. That loop IS the job.
