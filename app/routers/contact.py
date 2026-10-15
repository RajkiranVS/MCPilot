"""MCPilot — Contact Form Endpoint"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
import json, uuid
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/contact", tags=["Contact"])

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
    logger.info(f"CONTACT | name={payload.name} email={payload.email} vertical={payload.vertical}")
    try:
        import boto3
        s3  = boto3.client("s3", region_name="ap-south-1")
        key = f"contacts/{now.strftime('%Y-%m-%dT%H-%M-%S')}_{payload.name.replace(' ','_')}_{payload.vertical}.json"
        s3.put_object(Bucket="mcpilot.in", Key=key, Body=json.dumps(submission, indent=2), ContentType="application/json")
        logger.info(f"Saved to S3: {key}")
    except Exception as e:
        logger.error(f"S3 store failed: {e}")
    return {"status": "ok", "message": "Request received. We will respond within 24 hours."}

@router.get("/submissions")
async def list_submissions(request: Request) -> dict:
    scopes = getattr(request.state, "scopes", [])
    if "admin" not in scopes:
        raise HTTPException(status_code=403, detail="Admin scope required")
    try:
        import boto3
        s3 = boto3.client("s3", region_name="ap-south-1")
        response = s3.list_objects_v2(Bucket="mcpilot.in", Prefix="contacts/")
        submissions = []
        for obj in response.get("Contents", []):
            body = s3.get_object(Bucket="mcpilot.in", Key=obj["Key"])
            submissions.append(json.loads(body["Body"].read()))
        submissions.sort(key=lambda x: x["submitted"], reverse=True)
        return {"total": len(submissions), "submissions": submissions}
    except Exception as e:
        logger.error(f"S3 list failed: {e}")
        return {"total": 0, "submissions": [], "error": "Failed to load submissions"}
