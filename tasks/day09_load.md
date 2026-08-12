# Day 9 — Build the Load Step

🎯 **Goal:** load clean data into PostgreSQL in a way that is always safe to re-run.

## What you'll learn
- Upserts: insert-or-update in one statement
- Why "attempted" and "actually written" are different numbers

## Your tasks

**1. Create `etl/load.py`.** Connect using your `.env` values:
```python
import psycopg2
conn = psycopg2.connect(host=..., dbname="nexora_health", user="nexora", password=...)
```

**2. Remember Day 5?** Dimensions arrive as snapshots (same rows every week), facts as new events. That gives us two loading strategies:

- **Dimensions** (patients, organizations, providers, payers): if the id already exists, just update the row.
```sql
INSERT INTO patients (id, birthdate, ...) VALUES %s
ON CONFLICT (id) DO UPDATE SET birthdate = EXCLUDED.birthdate, ...
```
- **Facts** (encounters, conditions): a visit that happened is history — if we've seen it, skip it.
```sql
INSERT INTO encounters (...) VALUES %s
ON CONFLICT (id) DO NOTHING
```

**3. Load fast with `execute_values`:**
```python
from psycopg2.extras import execute_values
rows = list(df.itertuples(index=False, name=None))
written = execute_values(cur, sql + " RETURNING 1", rows, fetch=True)
loaded = len(written)
```
That `RETURNING 1` matters: with `DO NOTHING`, skipped rows return nothing — so `loaded` counts what was **actually written**, not what you attempted. Honest numbers.

**4. One transaction per dataset.** Commit after each dataset finishes. If conditions fails at the end, the five datasets before it stay loaded — you fix the problem and re-run just fine (because re-runs are safe now!).

**5. Load in the Day 7 order** — organizations first, conditions last — or the database's foreign keys will complain.

**6. Test by hand** with one dataset:
```python
loaded = load(conn, "organizations", transformed_df)
print(loaded)   # 283 the first time...
loaded = load(conn, "organizations", transformed_df)
print(loaded)   # ...and it still says 283 (updates). Now try encounters twice: second time = 0. 
```

## ✅ You're done when
- [ ] All 6 datasets load without errors
- [ ] Loading encounters twice writes 0 the second time
- [ ] Loading patients twice updates instead of crashing
- [ ] Committed

## 💡 Tip
If you get a foreign-key error while loading, your load order is wrong or your Day 7 validation let something through — go look at which.
