import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import AuthSession, Membership, User
from app.infra.database import get_db
from app.modules.tenancy.auth import bearer


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def cipher() -> Fernet:
    return Fernet(get_settings().github_token_encryption_key.get_secret_value().encode())


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@dataclass(frozen=True)
class Principal:
    user_id: int
    tenant_id: int
    github_id: int | None
    token: str | None
    session_hash: str | None
    demo: bool = False


def principal(request: Request, credential: HTTPAuthorizationCredentials | None = Depends(bearer),
              db: Session = Depends(get_db)) -> Principal:
    config = get_settings()
    raw_session = request.cookies.get("rp_session")
    if raw_session and config.github_oauth_enabled:
        row = db.get(AuthSession, digest(raw_session))
        if row and row.revoked_at is None and utc(row.expires_at) > datetime.now(timezone.utc):
            user = db.get(User, row.user_id)
            if user and db.get(Membership, (row.tenant_id, row.user_id)):
                try:
                    token = cipher().decrypt(row.github_token_ciphertext.encode()).decode()
                except (InvalidToken, ValueError, UnicodeError):
                    raise HTTPException(401, "Authentication required") from None
                return Principal(user.id, row.tenant_id, user.github_user_id, token, row.id_hash)
    if config.demo_auth_enabled and config.app_env != "production" and credential:
        if hmac.compare_digest(credential.credentials.encode(),
                               config.demo_api_token.get_secret_value().encode()):
            membership = db.get(Membership, (config.demo_tenant_id, config.demo_user_id))
            if not membership:
                raise HTTPException(403, "Tenant membership required")
            return Principal(config.demo_user_id, membership.tenant_id, None, None, None, True)
    raise HTTPException(401, "Authentication required")


def require_csrf(request: Request, identity: Principal, db: Session):
    if identity.demo or not identity.session_hash:
        raise HTTPException(403, "Session required")
    if request.headers.get("origin") != get_settings().web_origin.rstrip("/"):
        raise HTTPException(403, "Invalid request origin")
    supplied = request.headers.get("x-csrf-token", "")
    cookie = request.cookies.get("rp_csrf", "")
    # Serialize mutations against logout; refresh the row after acquiring the lock.
    session = db.scalar(select(AuthSession).where(
        AuthSession.id_hash == identity.session_hash).with_for_update().execution_options(populate_existing=True))
    if (not supplied or not cookie or not session or session.revoked_at is not None
            or utc(session.expires_at) <= datetime.now(timezone.utc) or
            not hmac.compare_digest(supplied.encode(), cookie.encode()) or
            not hmac.compare_digest(digest(supplied), session.csrf_hash)):
        raise HTTPException(403, "Invalid CSRF token")
