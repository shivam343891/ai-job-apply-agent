"""
Pattern-matching auto-answer engine for application form fields.
All answers come from the candidate config + answer bank — no AI calls.
"""
import re
from playwright.async_api import Page, ElementHandle


def build_context_from_config(cfg, answer_bank: dict | None = None) -> dict:
    """
    Build the flat context dict that all form-filling functions use.
    answer_bank values override config defaults when present.
    """
    ab = answer_bank or {}

    ctx = {
        "first_name": cfg.first_name,
        "last_name": cfg.last_name,
        "full_name": cfg.full_name,
        "preferred_name": cfg.preferred_name or cfg.first_name,
        "email": cfg.email,
        "phone": cfg.phone,
        "location": cfg.location,
        "city": cfg.city,
        "state": cfg.state,
        "country": cfg.country,
        "postal_code": cfg.postal_code,
        "address": cfg.address,
        "linkedin": cfg.linkedin,
        "github": cfg.github,
        "website": cfg.website,
        "school": cfg.school,
        "major": cfg.major,
        "gpa": cfg.gpa,
        "gpa_range": cfg.gpa_range,
        "degree_type": cfg.degree_type,
        "graduation": cfg.graduation,
        "years_experience": cfg.years_experience,
        "current_company": cfg.current_company,
        "current_role": cfg.current_role,
        "pursuing_advanced_degree": cfg.pursuing_advanced_degree,
        "project_pitch": cfg.project_pitch,
        "authorized_to_work": "Yes" if cfg.authorized_to_work else "No",
        "require_current_sponsorship": "Yes" if cfg.require_current_sponsorship else "No",
        "require_future_sponsorship": "Yes" if cfg.require_future_sponsorship else "No",
        "eeo_gender": cfg.eeo_gender,
        "eeo_race": cfg.eeo_race,
        "eeo_veteran": cfg.eeo_veteran,
        "compensation": cfg.compensation,
        "start_date": cfg.start_date,
        # Convenience aliases used by rules below
        "how_did_you_hear": ab.get("how_did_you_hear", "LinkedIn"),
        "cover_letter": ab.get("cover_letter", ""),
        "work_auth_answer": ab.get("work_authorization", "Yes, I am authorized to work in the United States."),
        "sponsorship_current_answer": ab.get("sponsorship_current", "No" if not cfg.require_current_sponsorship else "Yes"),
        "sponsorship_future_answer": ab.get("sponsorship_future", "No" if not cfg.require_future_sponsorship else "Yes"),
        "relocation_answer": ab.get("willing_to_relocate", "Yes, I am open to relocating."),
        "remote_answer": ab.get("remote_preference", "Yes, I prefer remote work."),
        "travel_answer": ab.get("willing_to_travel", "Yes, I am willing to travel up to 20% if needed."),
        "salary_answer": ab.get("desired_compensation", cfg.compensation),
        "pitch": ab.get("software_pitch", cfg.project_pitch),
    }

    # Answer bank overrides for any key that matches directly
    for k, v in ab.items():
        if k not in ctx:
            ctx[k] = v

    return ctx


# ---------------------------------------------------------------------------
# Ordered regex rules: (pattern_on_label, context_key)
# ---------------------------------------------------------------------------
_TEXT_RULES: list[tuple[str, str]] = [
    (r"first\s*name", "first_name"),
    (r"last\s*name", "last_name"),
    (r"full\s*name|your name", "full_name"),
    (r"preferred\s*name|nickname", "preferred_name"),
    (r"email", "email"),
    (r"phone|telephone|mobile", "phone"),
    (r"city|current\s*city", "city"),
    (r"state|province", "state"),
    (r"zip|postal", "postal_code"),
    (r"address", "address"),
    (r"country", "country"),
    (r"location", "location"),
    (r"linkedin", "linkedin"),
    (r"github", "github"),
    (r"website|portfolio|personal\s*site", "website"),
    (r"university|school|college|institution", "school"),
    (r"degree|major|field\s*of\s*study", "major"),
    (r"gpa|grade\s*point", "gpa"),
    (r"graduation|expected\s*grad", "graduation"),
    (r"current\s*company|employer|organization", "current_company"),
    (r"current\s*(role|title|position|job)", "current_role"),
    (r"years.*experience|experience.*years", "years_experience"),
    (r"pursuing.*degree|advanced\s*degree", "pursuing_advanced_degree"),
    (r"salary|compensation|pay\s*expect", "salary_answer"),
    (r"start\s*date|available\s*to\s*start|availability", "start_date"),
    (r"how\s*did\s*you\s*hear|referral\s*source|source", "how_did_you_hear"),
    (r"cover\s*letter", "cover_letter"),
    (r"about\s*yourself|tell\s*us|summary|pitch|why\s*(do\s*you\s*want|are\s*you)", "pitch"),
    (r"authorized|eligible\s*to\s*work|work\s*auth", "work_auth_answer"),
    (r"sponsor.*current|current.*sponsor", "sponsorship_current_answer"),
    (r"sponsor.*future|future.*sponsor", "sponsorship_future_answer"),
    (r"reloc", "relocation_answer"),
    (r"travel", "travel_answer"),
]

_YES_NO_RULES: list[tuple[str, bool]] = [
    (r"authorized|eligible\s*to\s*work|work\s*authorization", True),
    (r"require.*current.*sponsor|current.*sponsor", False),
    (r"require.*future.*sponsor|future.*sponsor", False),
    (r"18\s*years|over\s*18|legal\s*age", True),
    (r"relocat", True),
    (r"remote", True),
    (r"background\s*check", True),
    (r"drug\s*test", True),
    (r"disability", False),
    (r"veteran", False),
]


def _match_text_rule(label: str) -> str | None:
    lower = label.lower()
    for pattern, key in _TEXT_RULES:
        if re.search(pattern, lower):
            return key
    return None


def _match_yes_no_rule(label: str) -> bool | None:
    lower = label.lower()
    for pattern, answer in _YES_NO_RULES:
        if re.search(pattern, lower):
            return answer
    return None


async def fill_text(page: Page, element: ElementHandle, label: str, context: dict) -> bool:
    key = _match_text_rule(label)
    if key and key in context and context[key]:
        await element.fill(str(context[key]))
        return True
    return False


async def pick_option(page: Page, element: ElementHandle, label: str, context: dict) -> bool:
    """Handle <select> dropdowns."""
    options = await element.query_selector_all("option")
    option_texts = [await o.inner_text() for o in options]

    # Check yes/no rules first
    want = _match_yes_no_rule(label)
    if want is not None:
        for i, text in enumerate(option_texts):
            t = text.strip().lower()
            if want and t in ("yes", "true", "1"):
                await element.select_option(index=i)
                return True
            if not want and t in ("no", "false", "0"):
                await element.select_option(index=i)
                return True

    # Try matching a text context value against option text
    key = _match_text_rule(label)
    if key and key in context:
        target = str(context[key]).lower()
        for i, text in enumerate(option_texts):
            if target in text.lower():
                await element.select_option(index=i)
                return True

    # Fallback: first non-placeholder option
    for i, text in enumerate(option_texts):
        stripped = text.strip()
        if stripped and stripped.lower() not in ("select...", "choose...", "-- select --", ""):
            await element.select_option(index=i)
            return True
    return False


async def pick_choice(page: Page, element: ElementHandle, label: str, context: dict) -> bool:
    """Handle radio buttons and checkboxes."""
    want = _match_yes_no_rule(label)
    if want is None:
        return False

    name = await element.get_attribute("name") or ""
    siblings = await page.query_selector_all(f"[name='{name}']") if name else [element]

    for sib in siblings:
        val = (await sib.get_attribute("value") or "").lower()
        if want and val in ("yes", "true", "1"):
            await sib.check()
            return True
        if not want and val in ("no", "false", "0"):
            await sib.check()
            return True
    return False
