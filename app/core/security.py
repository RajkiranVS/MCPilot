"""
MCPilot — Security Utilities
JWT creation/validation and API key hashing.
Kept separate from middleware so it can be tested independently.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from app.core.config import get_settings

settings = get_settings()

# ── Password / API key hashing ────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_secret(secret: str) -> str:
    """Hash an API key or password for storage."""
    return pwd_context.hash(secret)


def verify_secret(plain: str, hashed: str) -> bool:
    """Verify a plain secret against its hash."""
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────
class TokenPayload(BaseModel):
    sub: str            # subject — client_id or user_id
    tenant_id: str      # multi-tenant isolation
    scopes: list[str]   # e.g. ["gateway:invoke", "admin"]
    exp: Optional[int] = None


def create_access_token(
    subject: str,
    tenant_id: str,
    scopes: list[str],
    expires_minutes: int | None = None,
) -> str:
    """Create a signed JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "scopes": scopes,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT. Raises JWTError on failure.
    Called by AuthMiddleware — never raises HTTP exceptions directly.
    """
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.algorithm],
    )
    return TokenPayload(**payload)