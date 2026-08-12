# Day 11 — Prove Re-runs Are Safe

🎯 **Goal:** show — with real runs — that running the same data twice never duplicates anything.

## What you'll learn
- "Idempotent" — the fancy word for "safe to run again"
- How to read your own pipeline reports critically

## Your tasks

**1. Count first:**
```sql
SELECT count(*) FROM encounters;   -- write this number down
```

**2. Re-run the full load, exact same command:**
```bash
python -m etl.pipeline --source data/source --label full_load_rerun
```

**3. Read the report like a detective.** You should see something like:
- encounters: 7,210 read … **0 loaded** ← already there, all skipped. Correct!
- patients: 113 read … 113 loaded ← these are **updates**, not duplicates.

Count again — the number must not have moved:
```sql
SELECT count(*) FROM encounters;   -- same as before?
```

**4. Now run your weekly batches** from Day 5, one after another:
```bash
python -m etl.pipeline --source data/incoming/week_2026-06-01
python -m etl.pipeline --source data/incoming/week_2026-06-08
```
Question to answer honestly: these weeks load **0 new encounters**. Why is that correct and not a bug? (Hint: where did those encounters already come from?)

**5. Look at your run history:**
```sql
SELECT run_label, dataset_name, records_read, records_loaded, status
FROM etl_run_log ORDER BY log_id;
```
This table now tells the whole story of everything that ever happened. That's your audit trail.

**6. Write it down.** Add a short section to your README: "Why re-runs are safe" — 4–5 sentences in your own words. Think about the real world: a clinic emails "sorry, we sent the file twice!" — with your pipeline, the answer is "no problem". That's the whole point.

## ✅ You're done when
- [ ] Encounter count is identical before and after the re-run
- [ ] You can explain why weekly batches loaded 0 facts
- [ ] The README section is written
- [ ] Committed

## 💡 Tip
If the re-run DID duplicate something, check Day 9: is `ON CONFLICT` on the right columns for every table?
