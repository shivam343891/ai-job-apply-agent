import asyncio
import os
import sys
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from job_agent.routers import discovery, ai_skills, email, tracker
from job_agent.routers.apply import linkedin, lever, greenhouse, jobvite, ashby
from job_agent.jobs import router as jobs_router

# Playwright needs ProactorEventLoop on Windows to spawn subprocesses
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(title="AI Job Apply Agent", version="1.0.0")

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Config path is read from env var so the server knows which config to pre-fill in the UI
_CONFIG_PATH = os.environ.get("JOB_AGENT_CONFIG", Path(__file__).parent.joinpath("config.json").as_posix())


@app.get("/", response_class=HTMLResponse)
async def ui(request: Request):
    cfg_path = _CONFIG_PATH
    resume_path = ""
    preferences_path = ""
    csv_path = ""

    if cfg_path and Path(cfg_path).exists():
        import json
        data = json.loads(Path(cfg_path).read_text())
        # accept both camelCase and snake_case keys
        resume_path = data.get("resumePath") or data.get("resume_path", "")
        preferences_path = data.get("preferencesPath") or data.get("preferences_path", "")
        csv_path = data.get("csvPath") or data.get("csv_path", "")

    return _TEMPLATES.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "config_path": cfg_path,
            "resume_path": resume_path,
            "preferences_path": preferences_path,
            "csv_path": csv_path,
        },
    )


app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(discovery.router, prefix="/jobs", tags=["discovery"])
app.include_router(ai_skills.router, prefix="/resume", tags=["ai_skills"])
app.include_router(email.router, prefix="/email", tags=["email"])
app.include_router(tracker.router, prefix="/tracker", tags=["tracker"])
app.include_router(linkedin.router, prefix="/apply/linkedin", tags=["apply"])
app.include_router(lever.router, prefix="/apply/lever", tags=["apply"])
app.include_router(greenhouse.router, prefix="/apply/greenhouse", tags=["apply"])
app.include_router(jobvite.router, prefix="/apply/jobvite", tags=["apply"])
app.include_router(ashby.router, prefix="/apply/ashby", tags=["apply"])


@app.get("/health")
async def health():
    return {"status": "ok"}
