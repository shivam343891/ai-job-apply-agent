# Job Search Agent — Candidate Profile

Last updated: YYYY-MM-DD

## Candidate

- Name: YOUR_FIRST_NAME YOUR_LAST_NAME
- Email: YOUR_EMAIL
- Phone: YOUR_PHONE
- Location: YOUR_CITY, YOUR_STATE
- LinkedIn: https://linkedin.com/in/YOUR_HANDLE
- GitHub: https://github.com/YOUR_HANDLE
- Website: https://YOUR_SITE
- School: YOUR_UNIVERSITY
- Degree: YOUR_DEGREE (YOUR_MAJOR)
- Graduation: YOUR_GRADUATION_DATE
- GPA: YOUR_GPA / 4.000
- Citizenship: YOUR_CITIZENSHIP
- Authorized to work in the US: Yes / No
- Visa status: YOUR_VISA_STATUS
- Require current sponsorship: Yes / No
- Require future sponsorship: Yes / No
- Willing to relocate: Yes / No
- Willing to work on-site: Yes / No
- Willing to travel: Yes, up to ___%
- EEO: gender YOUR_GENDER, race YOUR_RACE, veteran No, disability No
- Desired compensation: $YOUR_RANGE

## Config files

- Agent config: /path/to/config.json
- Answer bank: /path/to/answer_bank.md
- Preferences: /path/to/preferences.json
- Resume (software): /path/to/software-resume.pdf
- Resume (general): /path/to/general-resume.pdf
- Application tracker CSV: /path/to/application-tracker.csv
- Google Sheet ID: YOUR_SHEET_ID

## Application rules

- Prefer truthful, submittable applications over aggressive volume.
- Skip roles gated behind US-citizen / green-card / security-clearance requirements
  unless the form truthfully accommodates your status.
- Use the software resume for SWE/ML/data roles; general resume otherwise.
- After each submission: update local CSV, sync Google Sheet, mark confirmation email read.
- If a form stalls behind CAPTCHA: log as "blocked — captcha", do not mark as submitted.
- autoSubmit is false by default — verify the form before enabling.

## Tracking

- Local CSV: application-tracker.csv
- Google Sheet: YOUR_SHEET_ID (sheet: Applications)
- API server: http://localhost:8000

## Current session state

- Last updated: YYYY-MM-DD
- Last action: (describe what was done)
- Pending: (list any pending manual applications or follow-ups)
- Known issues: (CAPTCHAs, blocked forms, etc.)

## Best next move

Describe what the next agent session should do — e.g.:
"Search for Python backend roles on LinkedIn and Indeed, score against preferences,
apply to High-rated results via the apply endpoints, then sync tracker."
