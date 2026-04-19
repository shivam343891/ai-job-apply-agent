"""Submission monitoring, captcha detection, and dry-run guard."""
import asyncio
from playwright.async_api import Page

CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    ".g-recaptcha",
    "#challenge-form",
]

SUBMIT_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    "button:has-text('Submit')",
    "button:has-text('Apply')",
    "button:has-text('Send Application')",
]


async def detect_captcha(page: Page) -> bool:
    for sel in CAPTCHA_SELECTORS:
        if await page.query_selector(sel):
            return True
    return False


async def click_submit(page: Page, auto_submit: bool) -> dict:
    if not auto_submit:
        return {"submitted": False, "reason": "dry_run"}

    for sel in SUBMIT_SELECTORS:
        btn = await page.query_selector(sel)
        if btn:
            await btn.click()
            return {"submitted": True, "selector": sel}
    return {"submitted": False, "reason": "no_submit_button_found"}


async def monitor_submission(page: Page, timeout: int = 180) -> dict:
    """Wait for confirmation or error after submission."""
    confirmation_patterns = [
        "application submitted",
        "thank you for applying",
        "your application has been received",
        "successfully applied",
    ]
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        content = (await page.content()).lower()
        for pat in confirmation_patterns:
            if pat in content:
                return {"confirmed": True, "pattern": pat}
        if await detect_captcha(page):
            return {"confirmed": False, "reason": "captcha_detected"}
        await asyncio.sleep(2)
    return {"confirmed": False, "reason": "timeout"}
