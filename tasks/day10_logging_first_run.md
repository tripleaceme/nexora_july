# Day 10 — Logging + Your First Full Run

🎯 **Goal:** glue all the steps into one command, make every run leave a paper trail, then run the whole thing for real.

## What you'll learn
- Python's logging module (goodbye, scattered print statements)
- Why every pipeline run needs an audit trail

## Your tasks

**1. Create the audit table.** Add to your schema (and run it):
```sql
CREATE TABLE etl_run_log (
    log_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id text, run_label text, dataset_name text,
    records_read int, records_rejected int, records_loaded int,
    started_at timestamptz, finished_at timestamptz, status text
);
```

**2. Set up logging** so messages go to the screen AND a file:
```python
import logging, sys
logging.basicConfig(
    level="INFO",
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(f"logs/run_{run_id}.log")])
```
Then sprinkle useful messages: `logging.info("extracted patients: %d rows", len(df))`.

**3. Build the orchestrator: `etl/pipeline.py`.** For each dataset, in order: extract → validate → transform → load → insert one row into `etl_run_log`. Generate one `run_id` (timestamp) for the whole run. Add a command-line interface:
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--source", default="data/source")
parser.add_argument("--label", default="run")
```

**4. Write the validation report.** At the end of the run, write `reports/validation_report_<run_id>.md`: a small table with read / valid / rejected / loaded per dataset, and the list of rejection reasons (if any). This becomes a deliverable on Day 12.

**5. 🚀 Run it:**
```bash
python -m etl.pipeline --source data/source --label full_load
```
Expected: ~12,600 rows read across the 6 datasets, 0 rejected, everything loaded.

**6. Check the paper trail.** Look at the log file, the report, and:
```sql
SELECT dataset_name, records_read, records_loaded FROM etl_run_log;
SELECT count(*) FROM encounters;   -- 7210?
```

## ✅ You're done when
- [ ] One command runs the entire pipeline
- [ ] `etl_run_log` has 6 rows for your run
- [ ] The log file and validation report exist and make sense
- [ ] encounters has 7,210 rows in the database
- [ ] Committed

## 💡 Tip
Congratulations — you have a working ETL pipeline! 🎉 Week 3 is about proving how good it is.
