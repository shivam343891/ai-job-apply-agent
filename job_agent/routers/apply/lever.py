"""
Lever application automation — single-page form.
  POST /apply/lever/apply → async, returns job_id
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from job_agent import jobs as job_store
from job_agent.config import load_config
from job_agent.automation.browser import launch_browser
from job_agent.automation.answer_engine import fill_text, pick_option, build_context_from_config
from job_agent.config import load_answer_bank
from job_agent.automation.submission import detect_captcha, click_submit, monitor_submission

router = APIRouter()


class LeverApplyRequest(BaseModel):
    job_url: str
    config_path: str


async def _fill_location_via_api(page, location: str) -> bool:
    """Use Lever's internal location search API."""
    import httpx
    base_url = page.url.split("/apply")[0]
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base_url}/api/v1/locations",
            params={"q": location},
            timeout=5,
        )
        if resp.status_code == 200:
            results = resp.json()
            if results:
                loc_input = await page.query_selector("input[name='location']")
                if loc_input:
                    await loc_input.fill(results[0].get("text", location))
                    return True
    return False


async def _apply(job_id: str, req: LeverApplyRequest):
    cfg = load_config(req.config_path)
    answer_bank = load_answer_bank(cfg.answer_bank_path)
    ctx_data = build_context_from_config(cfg, answer_bank)
    events = []

    browser, ctx = await launch_browser(headless=False)
    page = await ctx.new_page()
    await page.goto(req.job_url, wait_until="networkidle")
    events.append({"stage": "navigate", "url": req.job_url})

    if await detect_captcha(page):
        await browser.close()
        return {"success": False, "reason": "captcha_on_load", "events": events}

    # Fill by name= attribute
    fields = await page.query_selector_all("input[name], textarea[name], select[name]")
    for el in fields:
        name = await el.get_attribute("name") or ""
        tag = await el.evaluate("el => el.tagName.toLowerCase()")
        if tag == "select":
            await pick_option(page, el, name, ctx_data)
        else:
            await fill_text(page, el, name, ctx_data)

    # Location via internal API
    await _fill_location_via_api(page, cfg.identity.location)

    # Resume upload
    resume_input = await page.query_selector("input[type='file']")
    if resume_input and cfg.resume_path:
        await resume_input.set_input_files(cfg.resume_path)
        events.append({"stage": "resume_uploaded"})

    if await detect_captcha(page):
        events.append({"issue": "hcaptcha_detected"})
        await browser.close()
        return {"success": False, "reason": "hcaptcha", "events": events}

    result = await click_submit(page, cfg.auto_submit)
    events.append({"stage": "submit", **result})

    if result.get("submitted"):
        monitor = await monitor_submission(page)
        events.append({"stage": "monitor", **monitor})

    await browser.close()
    return {"success": result.get("submitted", False), "events": events}


@router.post("/apply")
async def lever_apply(req: LeverApplyRequest, background_tasks: BackgroundTasks):
    job_id = job_store.create_job()
    background_tasks.add_task(job_store.run_background, job_id, _apply(job_id, req))
    return {"job_id": job_id, "status": "pending"}
