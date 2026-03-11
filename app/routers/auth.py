"""
MCPilot — Auth Router
Issues JWT tokens for clients that have a valid API key.
Allows clients to exchange their API key for a short-lived JWT.
"""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.core.security import create_access_token
from app.core.logging import get_logger
from app.middleware.auth import _API_KEY_STORE

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = get_logger(__name__)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Exchange API key for JWT",
    description=(
        "Clients with a valid API key can exchange it for a short-lived JWT. "
        "Use the JWT for subsequent /gateway/* requests."
    ),
)
async def issue_token(x_api_key: str = Header(...)) -> TokenResponse:
    key_data = _API_KEY_STORE.get(x_api_key)
    if not key_data:
        raise HTTPException(status_code=401, detail="Invalid API key")

    token = create_access_token(
        subject=key_data["client_id"],
        tenant_id=key_data["tenant_id"],
        scopes=key_data["scopes"],
    )
    logger.info(f"Token issued | client={key_data['client_id']}")
    return TokenResponse(
        access_token=token,
        expires_in_minutes=60,
    )