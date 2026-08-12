# Day 5 — Create Weekly Batches

🎯 **Goal:** a script that slices the big Synthea export into weekly folders — the way clinics would actually send us data.

## What you'll learn
- The difference between a **snapshot** (whole list, sent every week) and an **increment** (only new events)
- Working with dates and weeks in pandas

## Your tasks

**1. Understand the setup.** Synthea gave us ALL history in one file. But the case study says clinics send data **weekly**. So we'll simulate it: each weekly folder gets that week's encounters + conditions, plus a full copy of the four small files.

**2. Write `scripts/make_weekly_batches.py`.** The plan:
```python
# 1. read encounters.csv
# 2. parse the START column as a date
# 3. find each encounter's "week start" (its Monday)
# 4. take the last 4 complete weeks
# 5. for each week, create data/incoming/week_YYYY-MM-DD/ and write:
#    - encounters.csv  -> only that week's rows
#    - conditions.csv  -> only conditions whose ENCOUNTER id is in that week
#    - patients/organizations/providers/payers.csv -> full copies
```
Helpful trick for finding the Monday:
```python
start = pd.to_datetime(df["START"], utc=True, format="mixed")
monday = (start - pd.to_timedelta(start.dt.dayofweek, unit="D")).dt.date
```

**3. Run it and look inside a folder.** Open one week's encounters.csv — it should only have a handful of rows, all from the same 7 days.

**4. Now think about this** (write your answer in a comment at the top of the script):
- patients.csv arrives **complete every week** — a snapshot. Mostly the same people again and again.
- encounters.csv arrives with **only new visits** — an increment.

When we load week 2, the pipeline will see the same 113 patients again. Should it crash? Duplicate them? Update them? (Answer: update them quietly. You'll build exactly that on Day 9.)

## ✅ You're done when
- [ ] `data/incoming/` has 4 week folders, each with 6 CSVs
- [ ] Each week's encounters really are within one Mon–Sun range
- [ ] You wrote the snapshot vs increment answer in the script
- [ ] Committed (the script — the generated folders are gitignored)

## 💡 Tip
Weeks in this data are small (5–15 encounters). That's perfect — small batches are easy to check by hand while you build.
