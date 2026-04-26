"""
Layer 1 – Job Discovery
  POST /jobs/search   → scrapes India + remote-US/Europe in parallel, returns job_id
  POST /jobs/score    → synchronous fit scoring of provided job text
  POST /jobs/careers  → async company careers page scan via Playwright

Search strategy:
  - India: all locations, any work mode
  - US/Europe: remote only OR on-site with sponsorship flag in posting
  - Language filter: English-language postings only (LinkedIn/Indeed handle this)
  - Dedup across regions by job_url
"""
import asyncio
import re
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from job_agent import jobs as job_store
from job_agent.scoring.fit_scorer import load_preferences, score_job

router = APIRouter()

# Regions scraped on every search. Each entry is kwargs passed to scrape_jobs.
_REGIONS = [
    # India — all roles welcome
    {"location": "India", "country_indeed": "India", "is_remote": None},
    # US remote only
    {"location": "United States", "country_indeed": "USA", "is_remote": True},
    # Germany (strong tech market, English OK)
    {"location": "Germany", "country_indeed": "Germany", "is_remote": None},
    # Netherlands (English-first tech scene)
    {"location": "Netherlands", "country_indeed": "Netherlands", "is_remote": None},
    # UK
    {"location": "United Kingdom", "country_indeed": "UK", "is_remote": None},
    # Canada remote
    {"location": "Canada", "country_indeed": "Canada", "is_remote": True},
]

# Keywords that indicate sponsorship is available (used to keep on-site non-India roles)
_SPONSORSHIP_SIGNALS = re.compile(
    r"visa\s*sponsor|sponsorship\s*available|will\s*sponsor|h[\-\s]?1b|relocation\s*support",
    re.IGNORECASE,
)


class SearchRequest(BaseModel):
    search_term: str
    search_terms: list[str] = []    # if set, overrides search_term; each is a separate jobspy query
    results_per_region: int = 15    # scraped per region per search term
    hours_old: int = 72
    site_names: list[str] = ["linkedin", "indeed", "glassdoor", "zip_recruiter"]
    preferences_path: str = ""      # if set, each job gets a fit score
    regions: list[str] = []         # location names to include; empty = all regions


class SynonymRequest(BaseModel):
    search_term: str


class ScoreRequest(BaseModel):
    job_text: str
    preferences_path: str


class CareersRequest(BaseModel):
    careers_url: str
    preferences_path: str = ""


def _is_relevant(job: dict, region: dict) -> bool:
    """
    Drop non-India on-site roles that show no sponsorship signal.
    India roles always pass. Remote roles always pass.
    """
    if region["location"] == "India":
        return True
    if region.get("is_remote"):
        return True
    # On-site international: keep only if posting mentions sponsorship
    text = " ".join(str(v) for v in job.values()).lower()
    return bool(_SPONSORSHIP_SIGNALS.search(text))


async def _scrape_region(search_term: str, hours_old: int, site_names: list, results_wanted: int, region: dict) -> list[dict]:
    from jobspy import scrape_jobs  # type: ignore
    import concurrent.futures

    def _sync():
        kwargs = dict(
            site_name=site_names,
            search_term=search_term,
            location=region["location"],
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed=region["country_indeed"],
        )
        if region.get("is_remote") is not None:
            kwargs["is_remote"] = region["is_remote"]
        try:
            df = scrape_jobs(**kwargs)
            records = df.fillna("").to_dict(orient="records")
        except Exception:
            records = []
        return records

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        records = await loop.run_in_executor(pool, _sync)

    # Tag each record with its region and filter
    out = []
    for r in records:
        r["_region"] = region["location"]
        if _is_relevant(r, region):
            out.append(r)
    return out


async def _scrape(job_id: str, req: SearchRequest):
    prefs = load_preferences(req.preferences_path) if req.preferences_path else None

    # Resolve which terms to search — explicit list takes priority over single term
    terms = req.search_terms if req.search_terms else [req.search_term]

    # Filter to requested regions (empty list = all)
    active_regions = (
        [r for r in _REGIONS if r["location"] in req.regions]
        if req.regions else _REGIONS
    ) or _REGIONS

    # Scrape all (term × region) combinations concurrently
    job_store.update_job(job_id, status="running", progress=5)
    tasks = [
        _scrape_region(term, req.hours_old, req.site_names, req.results_per_region, region)
        for term in terms
        for region in active_regions
    ]
    all_batches = await asyncio.gather(*tasks, return_exceptions=True)

    # Merge and deduplicate across all terms and regions
    seen_keys: set[str] = set()
    merged: list[dict] = []
    for batch in all_batches:
        if isinstance(batch, Exception):
            continue
        for job in batch:
            url = str(job.get("job_url", ""))
            key = url or f"{job.get('company','')}|{job.get('title','')}|{job.get('location','')}"
            if key not in seen_keys:
                seen_keys.add(key)
                if prefs:
                    text = f"{job.get('title','')} {job.get('description','')} {job.get('location','')}"
                    job["fit"] = score_job(text, prefs)
                merged.append(job)

    # Sort: High first, then Medium, Low, unscored
    order = {"High": 0, "Medium": 1, "Low": 2, "Skip": 3}
    merged.sort(key=lambda j: order.get(j.get("fit", {}).get("rating", ""), 2))

    job_store.update_job(job_id, progress=100)
    return {"count": len(merged), "regions_scraped": len(active_regions), "terms_searched": len(terms), "jobs": merged}


async def _scrape_careers(job_id: str, req: CareersRequest):
    from playwright.async_api import async_playwright

    job_store.update_job(job_id, status="running", progress=10)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(req.careers_url, wait_until="networkidle")
        jobs_data = await page.evaluate("""() => {
            const results = [];
            const cards = document.querySelectorAll(
                '[class*="job"], [class*="position"], [class*="role"], [class*="opening"]'
            );
            cards.forEach(card => {
                const title = card.querySelector('h1,h2,h3,h4,a')?.innerText?.trim();
                const link = card.querySelector('a')?.href;
                const location = card.querySelector('[class*="location"]')?.innerText?.trim();
                if (title) results.push({ title, link: link || null, location: location || null });
            });
            return results;
        }""")
        await browser.close()

    prefs = load_preferences(req.preferences_path) if req.preferences_path else None
    jobs_out = []
    for job in jobs_data:
        entry = dict(job)
        if prefs:
            text = f"{job.get('title', '')} {job.get('location', '')}"
            entry["fit"] = score_job(text, prefs)
        jobs_out.append(entry)

    return {"count": len(jobs_out), "jobs": jobs_out, "source": req.careers_url}


@router.get("/regions")
async def list_regions():
    return {"regions": [r["location"] for r in _REGIONS]}


@router.post("/search")
async def search_jobs(req: SearchRequest, background_tasks: BackgroundTasks):
    job_id = job_store.create_job()
    background_tasks.add_task(job_store.run_background, job_id, _scrape(job_id, req))
    return {"job_id": job_id, "status": "pending"}


@router.post("/synonyms")
async def get_synonyms(req: SynonymRequest):
    """Return WordNet synonyms for each word in the search term so the UI can let the user pick."""
    try:
        import nltk  # type: ignore
        from nltk.corpus import wordnet  # type: ignore
        try:
            wordnet.synsets("test")
        except LookupError:
            nltk.download("wordnet", quiet=True)
            nltk.download("omw-1.4", quiet=True)
    except ImportError:
        return {"error": "nltk not installed. Run: pip install nltk", "words": {}}

    words = req.search_term.split()
    result: dict[str, list[str]] = {}
    for word in words:
        syns: set[str] = set()
        for synset in wordnet.synsets(word):
            for lemma in synset.lemmas():
                name = lemma.name().replace("_", " ")
                if name.lower() != word.lower():
                    syns.add(name)
        result[word] = sorted(syns)[:15]  # cap per word to keep UI manageable
    return {"words": result}


@router.post("/score")
async def score_job_fit(req: ScoreRequest):
    prefs = load_preferences(req.preferences_path)
    return score_job(req.job_text, prefs)


@router.post("/careers")
async def scan_careers(req: CareersRequest, background_tasks: BackgroundTasks):
    job_id = job_store.create_job()
    background_tasks.add_task(job_store.run_background, job_id, _scrape_careers(job_id, req))
    return {"job_id": job_id, "status": "pending"}
