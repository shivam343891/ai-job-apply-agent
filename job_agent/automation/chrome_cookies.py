"""Load LinkedIn cookies from a manually exported JSON file."""
import json
from pathlib import Path

_DEFAULT_CACHE = Path(__file__).parent.parent / "linkedin_cookies.json"


def get_linkedin_cookies(cache_path: str | None = None) -> list[dict]:
    """
    Load LinkedIn cookies from a JSON file exported via Cookie-Editor extension.

    To generate the file:
    1. Install Cookie-Editor extension in Chrome
    2. Go to linkedin.com (logged in)
    3. Click Cookie-Editor → Export → Export as JSON
    4. Save to job_agent/linkedin_cookies.json
    """
    cache = Path(cache_path) if cache_path else _DEFAULT_CACHE

    if not cache.exists():
        raise RuntimeError(
            f"LinkedIn cookies file not found: {cache}\n"
            "Export cookies from LinkedIn using the Cookie-Editor Chrome extension:\n"
            "  1. Go to linkedin.com (logged in)\n"
            "  2. Click Cookie-Editor extension → Export → Export as JSON\n"
            f"  3. Save to {cache}"
        )

    raw = json.loads(cache.read_text())

    # Cookie-Editor exports a list; normalize to Playwright format
    cookies = []
    for c in raw:
        cookie = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ".linkedin.com"),
            "path": c.get("path", "/"),
            "secure": c.get("secure", True),
            "httpOnly": c.get("httpOnly", False),
            "sameSite": c.get("sameSite", "None"),
        }
        if c.get("expirationDate"):
            cookie["expires"] = int(c["expirationDate"])
        elif c.get("expires"):
            cookie["expires"] = int(c["expires"])
        cookies.append(cookie)

    if not cookies:
        raise RuntimeError(f"Cookie file is empty: {cache}")

    return cookies
