# ai-job-apply-agent

An AI-powered job application agent that automates the end-to-end job search and application process. Built with FastAPI, Playwright, and Claude AI.

## Features

### Job Discovery
- Search job boards across configurable regions in parallel
- **Multi-term search with PNCs** — optionally expand a search term into all sub-phrase combinations (e.g. "Backend Engineer Python" → "Backend Engineer", "Backend Python", "Engineer Python", etc.) and run each as a separate query, deduped in results
- **Synonym expansion** — toggle on to generate WordNet synonyms per word; pick and choose which to include before searching
- Scrape company careers pages directly
- AI-powered job fit scoring against your preferences and resume

### Automated Applications
Supports form-filling and submission on:
- **LinkedIn** Easy Apply (with cookie-based auth from your local Chrome session)
- **Greenhouse**
- **Lever**
- **Jobvite**
- **Ashby**

### AI Resume & Cover Letter Tools
- Tailor your resume to a specific job description
- Generate personalized cover letters
- ATS score your resume against a job posting
- Analyze job descriptions for key requirements and gaps

### Application Tracking
- Sync applications to a Google Sheets tracker
- Update application statuses
- List and filter submitted applications

### Email Integration
- Search Outlook for recruiter emails and follow-ups
- Send emails via Outlook via browser automation

### Background Jobs
- All long-running tasks (scraping, applying) run as background jobs
- Poll job status via `/jobs/{job_id}`

## Architecture

```
job_agent/
├── main.py                  # FastAPI app, UI route
├── config.py                # AgentConfig, answer bank loader
├── jobs.py                  # Background job runner
├── automation/
│   ├── browser.py           # Playwright browser/CDP helpers
│   ├── chrome_cookies.py    # Extract LinkedIn cookies from Chrome
│   ├── answer_engine.py     # AI-driven form field filling
│   └── submission.py        # CAPTCHA detection, submit & monitor
├── routers/
│   ├── discovery.py         # Job search & fit scoring endpoints
│   ├── ai_skills.py         # Resume tailoring, cover letter, ATS
│   ├── email.py             # Outlook search & send
│   ├── tracker.py           # Google Sheets sync & status updates
│   └── apply/
│       ├── linkedin.py
│       ├── greenhouse.py
│       ├── lever.py
│       ├── jobvite.py
│       └── ashby.py
└── scoring/
    └── fit_scorer.py        # Preference-based job scoring
```

## Setup

### Prerequisites
- Python 3.12 (jobspy requires 3.12; not 3.13/3.14)
- Google Chrome (for cookie extraction and CDP automation)
- Playwright browsers installed

```bash
pip install -r job_agent/requirements.txt
playwright install chromium
```

`nltk` WordNet data is downloaded automatically on first use of the `/jobs/synonyms` endpoint. To pre-download manually:

```python
import nltk; nltk.download("wordnet"); nltk.download("omw-1.4")
```

### Configuration

Create a `config.json` (or set `JOB_AGENT_CONFIG` env var to a custom path):

```json
{
  "resumePath": "/path/to/resume.pdf",
  "preferencesPath": "/path/to/preferences.json",
  "csvPath": "/path/to/applications.csv",
  "firstName": "Jane",
  "lastName": "Doe",
  "email": "jane@example.com",
  "phone": "555-555-5555",
  "linkedinUrl": "https://linkedin.com/in/janedoe"
}
```

### Running

```bash
uvicorn job_agent.main:app --reload
```

Open `http://127.0.0.1:8000` in your browser.

> **Windows note:** The app sets `WindowsProactorEventLoopPolicy` automatically so Playwright subprocess spawning works correctly. Run via terminal (`uvicorn`), not the VS Code debugpy launcher.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI |
| GET | `/health` | Health check |
| POST | `/jobs/search` | Search job boards (supports `search_terms` list for PNC/synonym multi-query) |
| POST | `/jobs/synonyms` | Generate WordNet synonyms for each word in a search term |
| POST | `/jobs/score` | Score a job against preferences |
| POST | `/jobs/careers` | Scrape a company careers page |
| POST | `/resume/tailor` | Tailor resume to a JD |
| POST | `/resume/cover-letter` | Generate cover letter |
| POST | `/resume/ats-score` | ATS score resume vs JD |
| POST | `/resume/analyze-jd` | Analyze job description |
| POST | `/apply/linkedin` | Apply via LinkedIn Easy Apply |
| POST | `/apply/greenhouse` | Apply via Greenhouse |
| POST | `/apply/lever` | Apply via Lever |
| POST | `/apply/jobvite` | Apply via Jobvite |
| POST | `/apply/ashby` | Apply via Ashby |
| POST | `/tracker/sync` | Sync applications to Google Sheets |
| POST | `/tracker/update` | Update application status |
| GET | `/tracker/list` | List tracked applications |
| POST | `/email/search` | Search Outlook emails |
| POST | `/email/send` | Send email via Outlook |
| GET | `/jobs/{job_id}` | Poll background job status |
