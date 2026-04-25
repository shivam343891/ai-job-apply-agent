"""Browser launch and CDP connect helpers."""
import asyncio
import concurrent.futures
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


def run_playwright_sync(async_fn, *args, **kwargs):
    """
    Run an async Playwright coroutine in a dedicated thread with its own
    ProactorEventLoop. Required on Windows because Playwright needs to spawn
    subprocesses, which fails inside FastAPI's already-running loop.
    """
    def _thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_fn(*args, **kwargs))
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_thread)
        return future.result()


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
