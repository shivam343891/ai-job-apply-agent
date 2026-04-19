"""
Layer 4 – Email via Outlook Web CDP
  POST /email/search   → search inbox, extract sender+body, mark read
  POST /email/send     → compose and send email
Both connect to a locally running Chrome instance.
"""
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from job_agent.automation.browser import connect_cdp

router = APIRouter()


class EmailSearchRequest(BaseModel):
    query: str
    max_results: int = 10
    mark_read: bool = True
    debug_port: int = 9222


class EmailSendRequest(BaseModel):
    to: str
    subject: str
    body: str
    attachment_path: str = ""
    debug_port: int = 9222


async def _outlook_search(req: EmailSearchRequest) -> list[dict]:
    browser, context = await connect_cdp(req.debug_port)
    page = await context.new_page()
    await page.goto("https://outlook.live.com/mail/0/", wait_until="networkidle")

    # Type in search box
    search = await page.wait_for_selector("input[aria-label*='Search']", timeout=10000)
    await search.fill(req.query)
    await search.press("Enter")
    await page.wait_for_timeout(3000)

    # Extract messages
    items = await page.query_selector_all("[data-convid]")
    results = []
    for item in items[: req.max_results]:
        sender_el = await item.query_selector("[class*='from']")
        subject_el = await item.query_selector("[class*='subject']")
        preview_el = await item.query_selector("[class*='preview']")
        sender = await sender_el.inner_text() if sender_el else ""
        subject = await subject_el.inner_text() if subject_el else ""
        preview = await preview_el.inner_text() if preview_el else ""

        if req.mark_read:
            await item.click()
            await page.wait_for_timeout(500)

        results.append({"sender": sender, "subject": subject, "preview": preview})

    # Clear search
    clear = await page.query_selector("[aria-label*='Clear search']")
    if clear:
        await clear.click()

    await browser.close()
    return results


async def _outlook_send(req: EmailSendRequest) -> dict:
    browser, context = await connect_cdp(req.debug_port)
    page = await context.new_page()
    await page.goto("https://outlook.live.com/mail/0/", wait_until="networkidle")

    # New message button
    compose = await page.wait_for_selector("button[aria-label*='New mail']", timeout=10000)
    await compose.click()
    await page.wait_for_timeout(1000)

    # Fill To
    to_field = await page.wait_for_selector("input[aria-label='To']", timeout=5000)
    await to_field.fill(req.to)
    await to_field.press("Tab")

    # Fill Subject
    subject_field = await page.query_selector("input[aria-label='Subject']")
    if subject_field:
        await subject_field.fill(req.subject)

    # Fill Body
    body_field = await page.query_selector("[aria-label='Message body']")
    if body_field:
        await body_field.click()
        await body_field.type(req.body)

    # Optional attachment
    if req.attachment_path:
        attach_btn = await page.query_selector("[aria-label*='Attach']")
        if attach_btn:
            async with page.expect_file_chooser() as fc_info:
                await attach_btn.click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(req.attachment_path)
            await page.wait_for_timeout(2000)

    # Send
    send_btn = await page.query_selector("[aria-label='Send']")
    if send_btn:
        await send_btn.click()
        await page.wait_for_timeout(2000)
        await browser.close()
        return {"sent": True}

    await browser.close()
    return {"sent": False, "reason": "send_button_not_found"}


@router.post("/search")
async def search_email(req: EmailSearchRequest):
    results = await _outlook_search(req)
    return {"count": len(results), "messages": results}


@router.post("/send")
async def send_email(req: EmailSendRequest):
    result = await _outlook_send(req)
    return result
