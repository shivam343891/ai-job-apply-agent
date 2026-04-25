"""
Greenhouse application automation — single-page form.
  POST /apply/greenhouse/apply → async, returns job_id
"""
import asyncio
import concurrent.futures
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from job_agent import jobs as job_store
from job_agent.config import load_config, load_answer_bank
from job_agent.automation.answer_engine import fill_text, build_context_from_config
from job_agent.automation.submission import detect_captcha, click_submit, monitor_submission

router = APIRouter()


class GreenhouseApplyRequest(BaseModel):
    job_url: str
    config_path: str


async def _fill_react_select(page, container_selector: str, value: str) -> bool:
    control = await page.query_selector(f"{container_selector} .Select-control, {container_selector} [class*='control']")
    if not control:
        return False
    await control.click()
    await page.wait_for_timeout(300)
    input_el = await page.query_selector(f"{container_selector} input")
    if input_el:
        await input_el.type(value)
        await page.wait_for_timeout(500)
    clicked = await page.evaluate("""(sel) => {
        const option = document.querySelector(sel + ' [class*="option"]');
        if (option) { option.click(); return true; }
        return false;
    }""", container_selector)
    return bool(clicked)


async def _playwright_apply(job_id: str, req: GreenhouseApplyRequest):
    from job_agent.automation.browser import launch_browser

    cfg = load_config(req.config_path)
    answer_bank = load_answer_bank(cfg.answer_bank_path)
    ctx_data = build_context_from_config(cfg, answer_bank)
    events = []

    browser, ctx = await launch_browser(headless=False)
    page = await ctx.new_page()
    await page.goto(req.job_url, wait_until="networkidle")
    events.append({"stage": "navigate", "url": req.job_url})

    fields = await page.query_selector_all("input[id], textarea[id]")
    for el in fields:
        el_id = await el.get_attribute("id") or ""
        await fill_text(page, el, el_id, ctx_data)

    react_selects = await page.query_selector_all("[class*='select--container'], [data-field*='country'], [data-field*='state']")
    for rs in react_selects:
        rs_id = await rs.get_attribute("data-field") or ""
        if "country" in rs_id.lower():
            await _fill_react_select(page, f"[data-field='{rs_id}']", "United States")
        elif "state" in rs_id.lower():
            state = cfg.identity.location.split(",")[-1].strip() if "," in cfg.identity.location else cfg.identity.location
            await _fill_react_select(page, f"[data-field='{rs_id}']", state)

    resume_input = await page.query_selector("input[type='file']")
    if resume_input and cfg.resume_path:
        await resume_input.set_input_files(cfg.resume_path)
        events.append({"stage": "resume_uploaded"})

    eeo_fields = {"gender": cfg.eeo.gender, "race": cfg.eeo.race, "veteran_status": cfg.eeo.veteran}
    for field_name, value in eeo_fields.items():
        if value:
            sel = await page.query_selector(f"select[name*='{field_name}'], select[id*='{field_name}']")
            if sel:
                try:
                    await sel.select_option(label=value)
                except Exception:
                    pass

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


def _run_in_thread(job_id: str, req: GreenhouseApplyRequest):
    loop = asyncio.new_event_loop()
    if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_playwright_apply(job_id, req))
    finally:
        loop.close()


async def _apply(job_id: str, req: GreenhouseApplyRequest):
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        result = await loop.run_in_executor(pool, _run_in_thread, job_id, req)
    return result


@router.post("/apply")
async def greenhouse_apply(req: GreenhouseApplyRequest, background_tasks: BackgroundTasks):
    job_id = job_store.create_job()
    background_tasks.add_task(job_store.run_background, job_id, _apply(job_id, req))
    return {"job_id": job_id, "status": "pending"}
