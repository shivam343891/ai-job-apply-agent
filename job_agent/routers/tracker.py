"""
Layer 5 – Application Tracking
  POST /tracker/sync          → append CSV rows to Google Sheets
  POST /tracker/update-status → update status+notes in Sheets and local CSV
  GET  /tracker/list          → list tracked applications from CSV
"""
import csv
import re
import unicodedata
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _dedup_key(company: str, role: str, location: str) -> str:
    return "|".join([_normalize(company), _normalize(role), _normalize(location)])


def _get_sheets_service(credentials_path: str):
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import pickle
    import os

    token_path = Path(credentials_path).parent / "token.pkl"
    creds = None
    if token_path.exists():
        with open(token_path, "rb") as f:
            creds = pickle.load(f)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)
    return build("sheets", "v4", credentials=creds)


class SyncRequest(BaseModel):
    csv_path: str
    spreadsheet_id: str
    sheet_name: str = "Applications"
    credentials_path: str


class UpdateStatusRequest(BaseModel):
    company: str
    role: str
    location: str = ""
    new_status: str
    notes: str = ""
    csv_path: str
    spreadsheet_id: str
    sheet_name: str = "Applications"
    credentials_path: str


class ListRequest(BaseModel):
    csv_path: str


@router.post("/sync")
async def sync_to_sheets(req: SyncRequest):
    rows = []
    with open(req.csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {"synced": 0}

    service = _get_sheets_service(req.credentials_path)
    sheet = service.spreadsheets()

    # Get existing sheet data to deduplicate
    existing = sheet.values().get(
        spreadsheetId=req.spreadsheet_id,
        range=f"{req.sheet_name}!A:Z"
    ).execute().get("values", [])

    headers = existing[0] if existing else list(rows[0].keys())
    existing_keys = set()
    col_company = headers.index("company") if "company" in headers else 0
    col_role = headers.index("role") if "role" in headers else 1
    col_location = headers.index("location") if "location" in headers else 2

    for row in existing[1:]:
        if len(row) > col_location:
            key = _dedup_key(row[col_company], row[col_role], row[col_location])
            existing_keys.add(key)

    new_rows = []
    for row in rows:
        key = _dedup_key(
            row.get("company", ""),
            row.get("role", ""),
            row.get("location", ""),
        )
        if key not in existing_keys:
            new_rows.append([row.get(h, "") for h in headers])
            existing_keys.add(key)

    if not existing:
        new_rows.insert(0, headers)

    if new_rows:
        sheet.values().append(
            spreadsheetId=req.spreadsheet_id,
            range=f"{req.sheet_name}!A1",
            valueInputOption="RAW",
            body={"values": new_rows},
        ).execute()

    return {"synced": len(new_rows)}


@router.post("/update-status")
async def update_status(req: UpdateStatusRequest):
    # Update local CSV
    rows = []
    updated_csv = False
    with open(req.csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    target_key = _dedup_key(req.company, req.role, req.location)
    csv_row_idx = None
    for i, row in enumerate(rows):
        key = _dedup_key(
            row.get("company", ""),
            row.get("role", ""),
            row.get("location", ""),
        )
        if key == target_key:
            rows[i]["status"] = req.new_status
            rows[i]["notes"] = req.notes
            updated_csv = True
            csv_row_idx = i + 2  # 1-indexed + header row
            break

    if updated_csv:
        with open(req.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # Update Google Sheets
    if csv_row_idx:
        service = _get_sheets_service(req.credentials_path)
        existing = service.spreadsheets().values().get(
            spreadsheetId=req.spreadsheet_id,
            range=f"{req.sheet_name}!A1:1"
        ).execute().get("values", [[]])
        headers = existing[0] if existing else []

        status_col = headers.index("status") if "status" in headers else None
        notes_col = headers.index("notes") if "notes" in headers else None

        updates = []
        if status_col is not None:
            col_letter = chr(ord("A") + status_col)
            updates.append({
                "range": f"{req.sheet_name}!{col_letter}{csv_row_idx}",
                "values": [[req.new_status]],
            })
        if notes_col is not None:
            col_letter = chr(ord("A") + notes_col)
            updates.append({
                "range": f"{req.sheet_name}!{col_letter}{csv_row_idx}",
                "values": [[req.notes]],
            })

        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=req.spreadsheet_id,
                body={"valueInputOption": "RAW", "data": updates},
            ).execute()

    return {"updated_csv": updated_csv, "sheet_row": csv_row_idx}


@router.get("/list")
async def list_applications(csv_path: str):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return {"count": len(rows), "applications": rows}
