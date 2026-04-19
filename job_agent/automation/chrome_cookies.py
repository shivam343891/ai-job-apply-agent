"""Extract LinkedIn cookies from Chrome and convert to Playwright-compatible JSON."""
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import browser_cookie3


def extract_linkedin_cookies() -> list[dict]:
    """
    Read LinkedIn cookies from Chrome using browser-cookie3 (handles DPAPI decryption on Windows).
    Returns a list of cookie dicts compatible with Playwright's add_cookies().
    """
    jar = browser_cookie3.chrome(domain_name=".linkedin.com")
    cookies = []
    for c in jar:
        cookie: dict = {
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": bool(c.secure),
            "httpOnly": False,
            "sameSite": "None",
        }
        if c.expires:
            cookie["expires"] = int(c.expires)
        cookies.append(cookie)
    return cookies


def get_linkedin_cookies(cache_path: str | None = None) -> list[dict]:
    """
    Return LinkedIn cookies, writing to cache_path if provided (for debugging/inspection).
    Raises RuntimeError if Chrome is open and the cookie DB is locked.
    """
    try:
        cookies = extract_linkedin_cookies()
    except Exception as e:
        raise RuntimeError(
            f"Failed to extract Chrome cookies: {e}\n"
            "Make sure Chrome is closed or try closing it and retrying."
        ) from e

    if not cookies:
        raise RuntimeError(
            "No LinkedIn cookies found in Chrome. "
            "Please log in to LinkedIn in Chrome first."
        )

    if cache_path:
        Path(cache_path).write_text(json.dumps(cookies, indent=2))

    return cookies
