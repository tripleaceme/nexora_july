# Day 3 — Design and Create the Database

🎯 **Goal:** a PostgreSQL database with all 6 tables, ready to receive data.

## What you'll learn
- What a star schema is (fact table in the middle, dimension tables around it)
- How database constraints protect you from bad data

## Your tasks

**1. Draw your star schema first.** On paper: `encounters` in the middle (the fact — one row per appointment). Around it: `patients`, `organizations`, `providers`, `payers` (the dimensions — who/where/how paid). `conditions` hangs off encounters (one row per diagnosis).

**2. Create the database and a user.** Save this as `sql/00_init_db.sql` and run it once:
```sql
CREATE ROLE nexora LOGIN PASSWORD 'pick_a_password';
CREATE DATABASE nexora_health OWNER nexora;
```
```bash
psql -U postgres -h localhost -f sql/00_init_db.sql
```

**3. Write the tables** in `sql/01_schema.sql`. Rules to follow:
- IDs are `uuid` — Postgres then refuses anything that isn't a real UUID. Free protection!
- Fields that must always exist get `NOT NULL` (a patient without a birthdate is not acceptable).
- Columns that point at other tables get `REFERENCES` (a foreign key).
- Use `CHECK` for things that are simply impossible, like an appointment that ends before it starts:
```sql
CHECK (stop_ts IS NULL OR stop_ts >= start_ts)
```
- `conditions.csv` has no ID column, so give the table an auto-generated one, plus a `UNIQUE (patient_id, encounter_id, code, start_date)` so the same diagnosis can't load twice.

**4. Think about order.** You can't create `encounters` before `patients` exists (the foreign key would point at nothing). Write the tables in this order: organizations, providers, payers, patients, encounters, conditions.

**5. Add a few indexes** on the columns you'll filter and join on a lot:
```sql
CREATE INDEX idx_encounters_patient ON encounters (patient_id);
CREATE INDEX idx_encounters_start ON encounters (start_ts);
```

**6. Run it and check:**
```bash
psql -U nexora -h localhost -d nexora_health -f sql/01_schema.sql
psql -U nexora -h localhost -d nexora_health -c "\dt"
```
You should see your 6 tables.

## ✅ You're done when
- [ ] `\dt` lists all 6 tables
- [ ] Inserting an encounter with a fake patient id **fails** (try it — that failure is your foreign key working!)
- [ ] Both SQL files are committed

## 💡 Tip
Your Python code will also validate data before loading (Week 2). So why constraints too? Belt **and** suspenders: if your code ever has a bug, the database is the last line of defense.
