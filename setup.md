# Setup Guide

## Prerequisites

- Python 3.12 (not 3.13 or 3.14 — jobspy requires 3.12)
  Download: https://www.python.org/downloads/release/python-31210/
- Google Chrome (must be logged in to LinkedIn; cookies are read automatically)
- Claude Code CLI (optional, for resume tailoring and cover letter skills)

---

## 1. Create a Python 3.12 virtual environment

```powershell
# Windows
py -3.12 -m venv .venv
.venv\Scripts\activate
```

```bash
# Mac / Linux
python3.12 -m venv .venv
source .venv/bin/activate
```

---

## 2. Install dependencies

```bash
pip install -r job_agent/requirements.txt
```

---

## 3. Install Playwright browser

```bash
playwright install chromium
```

---

## 4. Configure your profile

```bash
# Copy and edit the config
cp job_agent/config.example.json my_config.json

# Copy and fill in your answer bank
cp job_agent/config/answer_bank.template.md my_answer_bank.md

# Copy and update the candidate profile (used by Claude Code sessions)
cp job_agent/config/candidate_profile.template.md candidate_profile.md

# Copy and customize job preferences
cp job_agent/preferences.example.json my_preferences.json
```

Edit `my_config.json` with your personal details. Key fields:
- `resumePath` — absolute path to your resume PDF
- `answerBankPath` — path to your `my_answer_bank.md`
- `preferencesPath` — path to your `my_preferences.json`
- `autoSubmit` — set `true` only after testing with `false` (dry-run)

---

## 5. Log in to LinkedIn in Chrome

LinkedIn Easy Apply requires you to be logged in. The agent reads your Chrome cookies automatically — no manual export needed. Just make sure you are logged in to LinkedIn in your Chrome browser before running the agent.

---

## 6. Start the API server

```bash
uvicorn job_agent.main:app --reload
```

Server runs at `http://localhost:8000`
Docs at `http://localhost:8000/docs`

---

## 7. Claude Code skills (resume tailoring & cover letters)

If you have Claude Code CLI installed, two skills are available in `.claude/commands/`:

```
/tailor-resume   — rewrites resume bullets to match a job description
/cover-letter    — generates a 250-350 word cover letter
```

These run entirely within Claude Code using your Claude Pro subscription — no API key needed, no extra cost.

---

## Quick test

```bash
# Health check
curl http://localhost:8000/health

# Score a job against your preferences
curl -X POST http://localhost:8000/jobs/score \
  -H "Content-Type: application/json" \
  -d '{"job_text": "Python backend engineer, remote, FastAPI, AWS", "preferences_path": "/abs/path/my_preferences.json"}'

# ATS keyword analysis (no API key needed)
curl -X POST http://localhost:8000/resume/ats-score \
  -H "Content-Type: application/json" \
  -d '{"resume_path": "/abs/path/resume.txt", "job_description": "Python FastAPI AWS Kubernetes..."}'
```

---

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /jobs/search | Scrape jobs (returns job_id) |
| GET | /jobs/{id}/status | Poll background job |
| POST | /jobs/score | Score job text against preferences |
| POST | /jobs/careers | Scrape company careers page |
| POST | /resume/ats-score | Keyword gap analysis |
| POST | /resume/analyze-jd | Match score + narrative |
| POST | /resume/tailor | Instructions to use /tailor-resume skill |
| POST | /resume/cover-letter | Instructions to use /cover-letter skill |
| POST | /apply/linkedin/apply | LinkedIn Easy Apply (returns job_id) |
| POST | /apply/lever/apply | Lever application (returns job_id) |
| POST | /apply/greenhouse/apply | Greenhouse application (returns job_id) |
| POST | /apply/jobvite/apply | Jobvite application (returns job_id) |
| POST | /apply/ashby/apply | Ashby application (returns job_id) |
| POST | /email/search | Search Outlook inbox via CDP |
| POST | /email/send | Send email via Outlook CDP |
| POST | /tracker/sync | Sync CSV to Google Sheets |
| POST | /tracker/update-status | Update application status |
| GET | /tracker/list | List all tracked applications |
