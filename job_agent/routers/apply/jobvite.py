"""
Jobvite application automation.
Has a residence/consent gate before the main form.
  POST /apply/jobvite/apply → async, returns job_id
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


class JobviteApplyRequest(BaseModel):
    job_url: str
    config_path: str


async def _handle_residence_gate(page, cfg) -> bool:
    """Handle Jobvite's residence/consent gate if present."""
    # Residence country select
    country_sel = await page.query_selector("select[name*='country'], select[id*='country']")
    if country_sel:
        try:
            await country_sel.select_option(label="United States")
        except Exception:
            pass

    # Consent checkbox
    consent = await page.query_selector("input[type='checkbox'][name*='consent'], input[type='checkbox'][id*='consent']")
    if consent:
        await consent.check()

    # Continue button
    continue_btn = await page.query_selector("button:has-text('Continue'), button:has-text('Next'), input[type='submit']")
    if continue_btn:
        await continue_btn.click()
        await page.wait_for_timeout(2000)
        return True
    return False


async def _apply(job_id: str, req: JobviteApplyRequest):
    cfg = load_config(req.config_path)
    answer_bank = load_answer_bank(cfg.answer_bank_path)
    ctx_data = build_context_from_config(cfg, answer_bank)
    events = []

    browser, ctx = await launch_browser(headless=False)
    page = await ctx.new_page()
    await page.goto(req.job_url, wait_until="networkidle")
    events.append({"stage": "navigate", "url": req.job_url})

    # Handle gate
    gate_handled = await _handle_residence_gate(page, cfg)
    if gate_handled:
        events.append({"stage": "residence_gate_passed"})
        await page.wait_for_load_state("networkidle")

    # Fill by id=
    fields = await page.query_selector_all("input[id], textarea[id], select[id]")
    for el in fields:
        el_id = await el.get_attribute("id") or ""
        tag = await el.evaluate("el => el.tagName.toLowerCase()")
        if tag == "select":
            await pick_option(page, el, el_id, ctx_data)
        else:
            await fill_text(page, el, el_id, ctx_data)

    # Resume upload
    resume_input = await page.query_selector("input[type='file']")
    if resume_input and cfg.resume_path:
        await resume_input.set_input_files(cfg.resume_path)
        events.append({"stage": "resume_uploaded"})

    if await detect_captcha(page):
        await browser.close()
        return {"success": False, "reason": "captcha", "events": events}

    result = await click_submit(page, cfg.auto_submit)
    events.append({"stage": "submit", **result})

    if result.get("submitted"):
        monitor = await monitor_submission(page)
        events.append({"stage": "monitor", **monitor})

    await browser.close()
    return {"success": result.get("submitted", False), "events": events}


@router.post("/apply")
async def jobvite_apply(req: JobviteApplyRequest, background_tasks: BackgroundTasks):
    job_id = job_store.create_job()
    background_tasks.add_task(job_store.run_background, job_id, _apply(job_id, req))
    return {"job_id": job_id, "status": "pending"}
