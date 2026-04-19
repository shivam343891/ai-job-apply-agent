"""
Layer 2 – Resume & JD analysis (deterministic, no API calls).

For actual resume tailoring and cover letter generation, use the
Claude Code skills:
  /tailor-resume   →  .claude/commands/tailor-resume.md
  /cover-letter    →  .claude/commands/cover-letter.md

These endpoints provide fast, offline keyword analysis.
"""
import re
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# Common English stop-words to exclude from keyword analysis
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "dare",
    "ought", "used", "able", "we", "you", "they", "i", "it", "its", "this",
    "that", "these", "those", "our", "your", "their", "my", "his", "her",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "few", "more", "most", "other", "some", "such", "than", "too", "very",
    "as", "if", "about", "above", "after", "also", "any", "because",
    "between", "during", "including", "into", "through", "when", "while",
    "who", "whom", "which", "what", "how", "all", "up", "out", "just",
    "work", "role", "position", "team", "company", "job", "experience",
}

MIN_WORD_LEN = 3


class TailorRequest(BaseModel):
    resume_path: str
    job_description: str
    job_title: str = ""


class CoverLetterRequest(BaseModel):
    resume_path: str
    job_description: str
    company_name: str = ""
    job_title: str = ""


class ATSRequest(BaseModel):
    resume_path: str
    job_description: str


class AnalyzeJDRequest(BaseModel):
    resume_path: str
    job_description: str


def _read(path: str) -> str:
    p = Path(path)
    if not path or not p.is_file():
        raise ValueError(f"Resume file not found: '{path}'. Set resumePath in your config.")
    if p.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(p))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return p.read_text(encoding="utf-8", errors="ignore")


def _keywords(text: str, top_n: int = 60) -> list[str]:
    """Extract meaningful keywords from text, ranked by frequency."""
    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.]*\b", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if len(w) >= MIN_WORD_LEN and w not in _STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: freq[w], reverse=True)
    return ranked[:top_n]


def _gap_analysis(resume: str, jd: str) -> dict:
    jd_kw = set(_keywords(jd))
    resume_kw = set(_keywords(resume, top_n=200))
    matched = sorted(jd_kw & resume_kw)
    missing = sorted(jd_kw - resume_kw)
    score = round(len(matched) / max(len(jd_kw), 1) * 100)
    return {"score": score, "matched": matched, "missing": missing}


@router.post("/ats-score")
async def ats_score(req: ATSRequest):
    resume = _read(req.resume_path)
    gap = _gap_analysis(resume, req.job_description)
    recommendations = []
    if gap["missing"]:
        top_missing = gap["missing"][:5]
        recommendations.append(f"Add these missing keywords: {', '.join(top_missing)}")
    if gap["score"] < 50:
        recommendations.append("Consider adding a skills section that mirrors the job description language.")
    if gap["score"] >= 75:
        recommendations.append("Strong keyword match — focus on quantifying achievements.")
    return {
        "score": gap["score"],
        "matched_keywords": gap["matched"],
        "missing_keywords": gap["missing"],
        "recommendations": recommendations,
    }


@router.post("/analyze-jd")
async def analyze_jd(req: AnalyzeJDRequest):
    resume = _read(req.resume_path)
    gap = _gap_analysis(resume, req.job_description)
    top_matched = gap["matched"][:3]
    top_missing = gap["missing"][:3]

    if top_matched and top_missing:
        narrative = (
            f"Your resume aligns on {', '.join(top_matched)}. "
            f"To strengthen your application, address these gaps: {', '.join(top_missing)}. "
            f"Use the /tailor-resume Claude Code skill to rewrite bullets that close these gaps."
        )
    elif top_matched:
        narrative = (
            f"Strong alignment on {', '.join(top_matched)}. "
            f"Use the /tailor-resume skill to mirror the job description language more precisely."
        )
    else:
        narrative = (
            "Low keyword overlap. Use the /tailor-resume Claude Code skill "
            "to rewrite your resume against this job description."
        )

    return {
        "match_score": gap["score"],
        "gap_list": gap["missing"],
        "positioning_narrative": narrative,
    }


@router.post("/tailor")
async def tailor_resume(req: TailorRequest):
    """
    Resume tailoring requires Claude Code.
    Run the /tailor-resume skill from the Claude Code CLI with your resume and JD.
    """
    gap = _gap_analysis(_read(req.resume_path), req.job_description)
    return {
        "message": "Use the Claude Code skill to tailor your resume: run /tailor-resume in Claude Code.",
        "job_title": req.job_title,
        "resume_path": req.resume_path,
        "quick_analysis": {
            "match_score": gap["score"],
            "top_missing_keywords": gap["missing"][:10],
            "top_matched_keywords": gap["matched"][:10],
        },
    }


@router.post("/cover-letter")
async def cover_letter(req: CoverLetterRequest):
    """
    Cover letter generation requires Claude Code.
    Run the /cover-letter skill from the Claude Code CLI.
    """
    gap = _gap_analysis(_read(req.resume_path), req.job_description)
    return {
        "message": "Use the Claude Code skill to generate your cover letter: run /cover-letter in Claude Code.",
        "company_name": req.company_name,
        "job_title": req.job_title,
        "resume_path": req.resume_path,
        "quick_analysis": {
            "match_score": gap["score"],
            "top_matched_keywords": gap["matched"][:8],
        },
    }
