"""
Ashby application automation.
Uses CSS selector-based fill, autocomplete fields, checkboxes, and toggle buttons.
  POST /apply/ashby/apply → async, returns job_id
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from job_agent import jobs as job_store
from job_agent.config import load_config
from job_agent.automation.browser import launch_browser
from job_agent.automation.answer_engine import fill_text, build_context_from_config
from job_agent.config import load_answer_bank
from job_agent.automation.submission import detect_captcha, click_submit, monitor_submission

router = APIRouter()


class AshbyApplyRequest(BaseModel):
    job_url: str
    config_path: str


async def _fill_autocomplete(page, selector: str, value: str) -> bool:
    """Ashby autocomplete: type value, wait for dropdown, click first option."""
    el = await page.query_selector(selector)
    if not el:
        return False
    await el.click()
    await el.type(value, delay=80)
    await page.wait_for_timeout(800)
    option = await page.query_selector("[role='option']:first-child, [class*='option']:first-child")
    if option:
        await option.click()
        return True
    await el.press("Enter")
    return True


async def _handle_toggles(page, cfg) -> None:
    """Handle Ashby toggle buttons for work auth, sponsorship, etc."""
    toggles = await page.query_selector_all("button[role='switch'], [class*='toggle']")
    for toggle in toggles:
        label_el = await page.query_selector(f"label[for='{await toggle.get_attribute('id') or ''}']")
        label = await label_el.inner_text() if label_el else (await toggle.get_attribute("aria-label") or "")
        label_lower = label.lower()

        current_state = (await toggle.get_attribute("aria-checked") or "false").lower() == "true"

        if "authorized" in label_lower or "eligible" in label_lower:
            if not current_state:
                await toggle.click()
        elif "sponsor" in label_lower:
            if current_state:
                await toggle.click()


async def _apply(job_id: str, req: AshbyApplyRequest):
    cfg = load_config(req.config_path)
    answer_bank = load_answer_bank(cfg.answer_bank_path)
    ctx_data = build_context_from_config(cfg, answer_bank)
    events = []

    browser, ctx = await launch_browser(headless=False)
    page = await ctx.new_page()
    await page.goto(req.job_url, wait_until="networkidle")
    events.append({"stage": "navigate", "url": req.job_url})

    # CSS selector-based text inputs
    text_fields = await page.query_selector_all(
        "input[data-testid], input[data-field], textarea[data-testid], textarea[data-field]"
    )
    for el in text_fields:
        field_key = (await el.get_attribute("data-testid") or await el.get_attribute("data-field") or "")
        await fill_text(page, el, field_key, ctx_data)

    # Standard inputs by placeholder / aria-label
    standard = await page.query_selector_all("input[placeholder], input[aria-label], textarea[aria-label]")
    for el in standard:
        label = (await el.get_attribute("placeholder") or await el.get_attribute("aria-label") or "")
        await fill_text(page, el, label, ctx_data)

    # Autocomplete for location
    await _fill_autocomplete(page, "input[placeholder*='ocation'], input[aria-label*='ocation']", cfg.identity.location)

    # Checkboxes
    checkboxes = await page.query_selector_all("input[type='checkbox']")
    for cb in checkboxes:
        cb_id = await cb.get_attribute("id") or ""
        label_el = await page.query_selector(f"label[for='{cb_id}']")
        label = await label_el.inner_text() if label_el else ""
        label_lower = label.lower()
        if "authorized" in label_lower or "consent" in label_lower or "agree" in label_lower:
            if not await cb.is_checked():
                await cb.check()
        elif "sponsor" in label_lower:
            if await cb.is_checked():
                await cb.uncheck()

    # Toggle buttons
    await _handle_toggles(page, cfg)

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
async def ashby_apply(req: AshbyApplyRequest, background_tasks: BackgroundTasks):
    job_id = job_store.create_job()
    background_tasks.add_task(job_store.run_background, job_id, _apply(job_id, req))
    return {"job_id": job_id, "status": "pending"}
