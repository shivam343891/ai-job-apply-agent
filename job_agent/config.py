import json
import re
from pathlib import Path
from pydantic import BaseModel, Field, model_validator


class AgentConfig(BaseModel):
    # Identity
    first_name: str = ""
    last_name: str = ""
    preferred_name: str = ""
    email: str
    phone: str
    location: str          # "City, State" — display form
    city: str = ""
    state: str = ""
    country: str = "United States"
    postal_code: str = ""
    address: str = ""

    # Online presence
    linkedin: str = ""
    github: str = ""
    website: str = ""

    # Education
    school: str = ""
    major: str = ""
    gpa: str = ""
    gpa_range: str = ""
    degree_type: str = "Bachelor's"
    degree_completed: str = "Yes"
    graduation: str = ""

    # Current employment
    current_company: str = ""
    current_role: str = ""

    # Experience
    years_experience: str = "0"
    pursuing_advanced_degree: str = "No"
    project_pitch: str = ""

    # Phone details (for international numbers)
    phone_national: str = ""
    phone_country_label: str = ""

    # Work authorization
    authorized_to_work: bool = True
    require_current_sponsorship: bool = False
    require_future_sponsorship: bool = False

    # EEO
    eeo_gender: str = ""
    eeo_race: str = ""
    eeo_veteran: str = "No"
    eeo_disability: str = "No"

    # Compensation / availability
    compensation: str = ""
    start_date: str = "Immediately"
    expected_graduation: str = ""

    # Paths
    resume_path: str = ""
    resume_variants: dict[str, str] = Field(default_factory=dict)
    answer_bank_path: str = ""
    preferences_path: str = ""

    # Google Sheets tracking
    spreadsheet_id: str = ""
    sheet_name: str = "Applications"

    # Behavior
    auto_submit: bool = False

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data: dict) -> dict:
        """Accept camelCase keys from reference-repo config format."""
        mapping = {
            "firstName": "first_name",
            "lastName": "last_name",
            "preferredName": "preferred_name",
            "postalCode": "postal_code",
            "currentCompany": "current_company",
            "currentRole": "current_role",
            "authorizedToWork": "authorized_to_work",
            "requireCurrentSponsorship": "require_current_sponsorship",
            "requireFutureSponsorship": "require_future_sponsorship",
            "pursuingAdvancedDegree": "pursuing_advanced_degree",
            "eeoGender": "eeo_gender",
            "eeoRace": "eeo_race",
            "eeoVeteran": "eeo_veteran",
            "eeoDisability": "eeo_disability",
            "yearsExperience": "years_experience",
            "projectPitch": "project_pitch",
            "gpaRange": "gpa_range",
            "degreeType": "degree_type",
            "degreeCompleted": "degree_completed",
            "expectedGraduation": "expected_graduation",
            "resumePath": "resume_path",
            "resumeVariants": "resume_variants",
            "answerBankPath": "answer_bank_path",
            "preferencesPath": "preferences_path",
            "autoSubmit": "auto_submit",
            "startDate": "start_date",
            "phoneNational": "phone_national",
            "phoneCountryLabel": "phone_country_label",
            "spreadsheetId": "spreadsheet_id",
            "sheetName": "sheet_name",
        }
        out = {}
        for k, v in data.items():
            out[mapping.get(k, k)] = v

        # Derive first/last from full name if not provided explicitly
        if not out.get("first_name") and not out.get("last_name"):
            full = out.get("name", "")
            parts = full.split(" ", 1)
            out.setdefault("first_name", parts[0])
            out.setdefault("last_name", parts[1] if len(parts) > 1 else "")

        # Derive location if not provided
        if not out.get("location"):
            city = out.get("city", "")
            state = out.get("state", "")
            out["location"] = f"{city}, {state}".strip(", ")

        # Normalize bool-as-string fields ("Yes"/"No" → True/False)
        for bool_field in ("authorized_to_work", "require_current_sponsorship", "require_future_sponsorship"):
            val = out.get(bool_field)
            if isinstance(val, str):
                out[bool_field] = val.strip().lower() in ("yes", "true", "1")

        return out

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def pick_resume(self, role_keywords: str = "") -> str:
        """Return the best resume path for a given role."""
        kw = role_keywords.lower()
        for variant_key, path in self.resume_variants.items():
            if variant_key.lower() in kw:
                return path
        return self.resume_path


def load_config(path: str) -> AgentConfig:
    data = json.loads(Path(path).read_text())
    return AgentConfig(**data)


def load_answer_bank(path: str) -> dict[str, str]:
    """
    Parse a markdown answer-bank file into a flat key→value dict.
    Lines of the form `- Key: Value` or `Key: Value` are captured.
    """
    if not path or not Path(path).exists():
        return {}
    text = Path(path).read_text(encoding="utf-8")
    result = {}
    for line in text.splitlines():
        line = line.strip().lstrip("- ")
        m = re.match(r"^([^:]+?):\s*(.+)$", line)
        if m:
            key = m.group(1).strip().lower().replace(" ", "_")
            result[key] = m.group(2).strip()
    return result
