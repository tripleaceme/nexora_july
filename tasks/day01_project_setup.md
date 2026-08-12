# Day 1 — Set Up Your Project

🎯 **Goal:** by the end of today you have a Git repo, a Python environment, and a working PostgreSQL — ready to build on.

## What you'll learn
- How a data engineering project is set up from scratch
- Why some files (like passwords) must never go into Git

## Your tasks

**1. Read the case study.** Read the Nexora Health case study once, start to finish. Write down in your own words: what problem are we solving? One important detail: in this project we treat each patient **encounter** as an **appointment**.

**2. Create your project folder and Git repo.**
```bash
mkdir nexora-pipeline && cd nexora-pipeline
git init
```

**3. Create a `.gitignore` file** with at least this in it:
```
.env
__pycache__/
venv/
logs/
data/incoming/
data/rejected/
.DS_Store
```
The `.env` file will hold your database password later. Passwords never go into Git. Ever.

**4. Set up Python.**
```bash
python3 -m venv venv
source venv/bin/activate
pip install pandas psycopg2-binary python-dotenv
pip freeze > requirements.txt
```

**5. Install PostgreSQL.**
- Mac: download from postgresql.org, or `brew install postgresql@16`
- Windows: download the installer from postgresql.org
- Remember the password you choose during install — write it somewhere safe (not in the repo!).

**6. Test that PostgreSQL works:**
```bash
psql -U postgres -h localhost -c "select version();"
```
If you see a version number, you're good.

**7. Make your first commit.**
```bash
git add .
git commit -m "Project setup"
```

## ✅ You're done when
- [ ] You can explain the business problem in 2–3 sentences
- [ ] `git log` shows your first commit
- [ ] `psql` connects and shows a version
- [ ] Your `.gitignore` includes `.env`

## 💡 Tip
If `psql` says "command not found", PostgreSQL's `bin` folder is not on your PATH. Find where it installed (e.g. `/Library/PostgreSQL/16/bin` on Mac) and add it to your PATH.
