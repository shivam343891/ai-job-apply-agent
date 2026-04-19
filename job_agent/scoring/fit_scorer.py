"""
4-stage fit scoring:
  1. Dealbreakers  → if any triggered → Skip
  2. Must-haves    → fraction met determines base score
  3. Nice-to-haves → adds bonus
  4. Final band    → High / Medium / Low / Skip
"""
import json
import re
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class Preferences:
    dealbreakers: list[str] = field(default_factory=list)
    must_haves: list[str] = field(default_factory=list)
    nice_to_haves: list[str] = field(default_factory=list)


def load_preferences(path: str) -> Preferences:
    data = json.loads(Path(path).read_text())
    return Preferences(
        dealbreakers=data.get("dealbreakers", []),
        must_haves=data.get("must_haves", []),
        nice_to_haves=data.get("nice_to_haves", []),
    )


def _contains(text: str, keyword: str) -> bool:
    return bool(re.search(re.escape(keyword.lower()), text.lower()))


def score_job(job_text: str, prefs: Preferences) -> dict:
    # Stage 1: dealbreakers
    for db in prefs.dealbreakers:
        if _contains(job_text, db):
            return {"rating": "Skip", "score": 0, "triggered_dealbreaker": db}

    # Stage 2: must-haves
    must_met = sum(1 for m in prefs.must_haves if _contains(job_text, m))
    must_total = len(prefs.must_haves) or 1
    must_score = must_met / must_total  # 0.0 – 1.0

    # Stage 3: nice-to-haves
    nice_met = sum(1 for n in prefs.nice_to_haves if _contains(job_text, n))
    nice_total = len(prefs.nice_to_haves) or 1
    nice_score = nice_met / nice_total

    composite = must_score * 0.7 + nice_score * 0.3

    # Stage 4: band
    if composite >= 0.75:
        rating = "High"
    elif composite >= 0.45:
        rating = "Medium"
    elif composite >= 0.2:
        rating = "Low"
    else:
        rating = "Skip"

    return {
        "rating": rating,
        "score": round(composite, 3),
        "must_haves_met": must_met,
        "must_haves_total": must_total,
        "nice_to_haves_met": nice_met,
        "nice_to_haves_total": nice_total,
    }
