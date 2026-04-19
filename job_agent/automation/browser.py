"""Browser launch and CDP connect helpers."""
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


async def launch_browser(headless: bool = False) -> tuple[Browser, BrowserContext]:
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=headless)
    context = await browser.new_context()
    return browser, context


async def connect_cdp(debug_port: int = 9222) -> tuple[Browser, BrowserContext]:
    """Connect to a locally running Chrome instance via CDP."""
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(f"http://localhost:{debug_port}")
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    return browser, context


async def load_linkedin_cookies(context: BrowserContext) -> None:
    """Auto-extract LinkedIn cookies from Chrome and inject into the browser context."""
    from job_agent.automation.chrome_cookies import get_linkedin_cookies
    cookies = get_linkedin_cookies()
    await context.add_cookies(cookies)


async def new_page(context: BrowserContext) -> Page:
    return await context.new_page()


async def close_browser(browser: Browser) -> None:
    await browser.close()
