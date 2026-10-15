"""MCPilot — Contact Form Endpoint"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from pathlib import Path
import json, uuid
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/contact", tags=["Contact"])


def _submissions_dir() -> Path:
    path = Path(get_settings().contact_submissions_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path

class ContactRequest(BaseModel):
    name:     str
    org:      str = ""
    email:    str
    vertical: str
    message:  str = ""

@router.post("/submit")
async def submit_contact(payload: ContactRequest, request: Request) -> dict:
    now = datetime.now(timezone.utc)
    submission = {
        "id":        str(uuid.uuid4())[:8],
        "name":      payload.name,
        "org":       payload.org or "Not provided",
        "email":     payload.email,
        "vertical":  payload.vertical,
        "message":   payload.message or "No message",
        "submitted": now.isoformat(),
    }
    logger.info(f"CONTACT | id={submission['id']} vertical={payload.vertical}")
    try:
        # Filename uses only server-generated values — never user input
        path = _submissions_dir() / f"{now.strftime('%Y-%m-%dT%H-%M-%S')}_{submission['id']}.json"
        path.write_text(json.dumps(submission, indent=2), encoding="utf-8")
        logger.info(f"Contact submission saved: {path.name}")
    except Exception as e:
        logger.error(f"Contact submission store failed: {e}")
    return {"status": "ok", "message": "Request received. We will respond within 24 hours."}

@router.get("/submissions")
async def list_submissions(request: Request) -> dict:
    scopes = getattr(request.state, "scopes", [])
    if "admin" not in scopes:
        raise HTTPException(status_code=403, detail="Admin scope required")
    try:
        submissions = [
            json.loads(f.read_text(encoding="utf-8"))
            for f in _submissions_dir().glob("*.json")
        ]
        submissions.sort(key=lambda x: x["submitted"], reverse=True)
        return {"total": len(submissions), "submissions": submissions}
    except Exception as e:
        logger.error(f"Contact submissions load failed: {e}")
        return {"total": 0, "submissions": [], "error": "Failed to load submissions"}
