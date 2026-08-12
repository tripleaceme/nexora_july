# Day 13 — Answer the Business Questions

🎯 **Goal:** the whole point of the pipeline — answer Nexora's 9 standing questions with SQL.

## What you'll learn
- Writing views (saved queries the business can reuse)
- JOINs and GROUP BY doing real work

## Your tasks

**1. Build 4 reporting views** (add them to your schema file and run it):

- `v_clinic_activity_summary` — per clinic: total appointments, unique patients. Starter:
```sql
CREATE VIEW v_clinic_activity_summary AS
SELECT o.name AS clinic_name,
       count(e.id) AS total_appointments,
       count(DISTINCT e.patient_id) AS unique_patients
FROM organizations o
LEFT JOIN encounters e ON e.organization_id = o.id
GROUP BY o.id, o.name;
```
- `v_provider_activity_summary` — per provider: name, speciality, clinic, total appointments
- `v_monthly_appointment_trends` — per month: appointment count (hint: `date_trunc('month', start_ts)`)
- `v_payer_coverage_summary` — per payer: appointments, total claim cost, total covered

**2. Write `sql/business_questions.sql`** — the 9 questions, each as one query with a comment above it:
1. How many patients are registered?
2. How many appointments in the reporting period?
3. Which clinics had the most appointments?
4. Which providers attended the most appointments?
5. How many unique patients visited each clinic?
6. What are the most common encounter classes?
7. How many appointments per month?
8. How are appointments spread across payers, and how much do payers cover?
9. What are the most common diagnoses?

Many of these are now just `SELECT ... FROM v_... ORDER BY ... LIMIT 10` — that's why we built views.

**3. Run the whole file:**
```bash
psql -U nexora -h localhost -d nexora_health -f sql/business_questions.sql
```

**4. Sanity-check two answers by hand.** Take your top clinic — re-count it directly:
```sql
SELECT count(*) FROM encounters e
JOIN organizations o ON o.id = e.organization_id
WHERE o.name = '<your top clinic>';
```
Same number? Good. Never trust a query you haven't cross-checked at least once.

**5. Expected ballparks:** 113 patients · 7,210 total encounters · ambulatory is the most common class (around half).

## ✅ You're done when
- [ ] All 4 views exist and return data
- [ ] All 9 questions run and give sensible answers
- [ ] You cross-checked at least two answers
- [ ] Committed

## 💡 Tip
LEFT JOIN vs JOIN matters here: with LEFT JOIN from organizations, a clinic with zero appointments still shows up (with 0). Ask yourself which behavior the business wants.
