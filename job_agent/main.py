from fastapi import FastAPI
from job_agent.routers import discovery, ai_skills, email, tracker
from job_agent.routers.apply import linkedin, lever, greenhouse, jobvite, ashby
from job_agent.jobs import router as jobs_router

app = FastAPI(title="AI Job Apply Agent", version="1.0.0")

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
