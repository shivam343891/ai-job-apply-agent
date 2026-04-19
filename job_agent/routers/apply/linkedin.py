"""
LinkedIn Easy Apply automation.
  POST /apply/linkedin/apply → async, returns job_id
"""
import asyncio
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from job_agent import jobs as job_store
from job_agent.config import load_config
from job_agent.automation.browser import launch_browser, load_linkedin_cookies
from job_agent.automation.answer_engine import fill_text, pick_option, pick_choice, build_context_from_config
from job_agent.config import load_answer_bank
from job_agent.automation.submission import detect_captcha, click_submit, monitor_submission

router = APIRouter()

MAX_STEPS = 12


class LinkedInApplyRequest(BaseModel):
    job_url: str
    config_path: str


async def _apply(job_id: str, req: LinkedInApplyRequest):
    cfg = load_config(req.config_path)
    answer_bank = load_answer_bank(cfg.answer_bank_path)
    context_data = build_context_from_config(cfg, answer_bank)
    events = []

    browser, ctx = await launch_browser(headless=False)
    await load_linkedin_cookies(ctx)

    page = await ctx.new_page()
    await page.goto(req.job_url, wait_until="networkidle")
    events.append({"stage": "navigate", "url": req.job_url})

    # Click Easy Apply button
    easy_apply = await page.query_selector("button.jobs-apply-button")
    if not easy_apply:
        await browser.close()
        return {"success": False, "reason": "easy_apply_button_not_found", "events": events}
    await easy_apply.click()
    events.append({"stage": "easy_apply_opened"})

    for step in range(MAX_STEPS):
        job_store.update_job(job_id, progress=int((step / MAX_STEPS) * 80))

        # Captcha check
        if await detect_captcha(page):
            events.append({"stage": f"step_{step}", "issue": "captcha_detected"})
            await browser.close()
            return {"success": False, "reason": "captcha", "events": events}

        # Fill all visible inputs
        inputs = await page.query_selector_all(
            "input:visible, select:visible, textarea:visible"
        )
        for el in inputs:
            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            el_type = (await el.get_attribute("type") or "text").lower()
            # Find label
            el_id = await el.get_attribute("id") or ""
            label_el = await page.query_selector(f"label[for='{el_id}']")
            label = await label_el.inner_text() if label_el else el_id

            if tag == "select":
                filled = await pick_option(page, el, label, context_data)
            elif el_type in ("radio", "checkbox"):
                filled = await pick_choice(page, el, label, context_data)
            else:
                filled = await fill_text(page, el, label, context_data)

            if not filled:
                events.append({"stage": f"step_{step}", "unfilled_field": label or el_id})

        events.append({"stage": f"step_{step}", "inputs_processed": len(inputs)})

        # Look for Next or Review/Submit button
        next_btn = await page.query_selector("button[aria-label='Continue to next step']")
        review_btn = await page.query_selector("button[aria-label='Review your application']")
        submit_btn = await page.query_selector("button[aria-label='Submit application']")

        if submit_btn:
            result = await click_submit(page, cfg.auto_submit)
            events.append({"stage": "submit", **result})
            if result.get("submitted"):
                monitor = await monitor_submission(page)
                events.append({"stage": "monitor", **monitor})
            await browser.close()
            return {"success": result.get("submitted", False), "events": events}

        if review_btn:
            await review_btn.click()
            await page.wait_for_timeout(1000)
            continue

        if next_btn:
            await next_btn.click()
            await page.wait_for_timeout(1000)
            continue

        # No navigation button — dialog may have closed
        break

    await browser.close()
    return {"success": False, "reason": "max_steps_reached", "events": events}


@router.post("/apply")
async def linkedin_apply(req: LinkedInApplyRequest, background_tasks: BackgroundTasks):
    job_id = job_store.create_job()
    background_tasks.add_task(job_store.run_background, job_id, _apply(job_id, req))
    return {"job_id": job_id, "status": "pending"}
