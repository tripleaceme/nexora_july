# Day 15 — Present and Hand Over

🎯 **Goal:** tell the story of what you built, show it running live, and submit everything.

## What you'll learn
- Presenting technical work to a mixed audience
- The art of the live demo (and its safety net)

## Your tasks

**1. Build a short deck** (10–12 slides is plenty):
1. The problem — clinics, spreadsheets, manual weekly reports
2. The data — 6 Synthea files, and what you deliberately excluded
3. Architecture — one picture: exports → ETL → PostgreSQL → reports
4. The star schema
5. How validation works — rules, reasons, quarantine
6. Why re-runs are safe (your Day 11 story)
7. The dirty-data drill — 9 planted, 9 caught
8. Business answers — your favorite 3 numbers from Day 13
9. What you'd build next
10. Demo!

**2. Rehearse the live demo.** The script:
```bash
# 1. a clean weekly batch — show the report: all loaded
python -m etl.pipeline --source data/incoming/week_2026-06-01

# 2. the dirty batch — show the report: 9 rejected, with reasons
python -m etl.pipeline --source data/incoming/week_2026-06-08_dirty

# 3. open data/rejected/<run_id>/ and show a rejection reason
# 4. one business question live in psql
psql -U nexora -d nexora_health -c "SELECT * FROM v_clinic_activity_summary ORDER BY total_appointments DESC LIMIT 5;"
```
Run through it twice today. **Safety net:** screenshot every step — if the live demo misbehaves, you present the screenshots calmly instead of debugging on stage.

**3. Prepare your "what's next" story.** Pick two and be ready to say a sentence about each:
- Schedule the weekly run automatically (cron, later Airflow)
- A dashboard on top of the reporting views
- Add one more dataset end-to-end (immunizations is a nice one — small and clean)
- The future scheduling module from the case study

**4. Final submission checklist:**
- [ ] GitHub repository (pushed, README polished)
- [ ] Python ETL pipeline (all four stages + CLI)
- [ ] PostgreSQL schema (init + schema SQL files)
- [ ] Dirty-batch validation report (Day 12 evidence)
- [ ] Logging + `etl_run_log` audit trail
- [ ] Documentation (README, pipeline doc, schema doc + ERD)
- [ ] `sql/business_questions.sql` — all 9 answered

## ✅ You're done when
- [ ] Deck ready, demo rehearsed twice, screenshots saved
- [ ] Every box in the submission checklist is ticked
- [ ] Repo pushed 🚀

## 💡 Tip
Nervous? Start the presentation with your dirty-batch story — "I broke my own data on purpose, and here's what happened." It's concrete, it's yours, and it shows exactly the engineering mindset this project was about.
