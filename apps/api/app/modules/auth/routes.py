import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import AuthSession, Membership, OAuthAttempt, PersonalTenant, Tenant, User
from app.infra.database import get_db
from app.modules.auth.session import Principal, cipher, digest, principal, require_csrf
from app.modules.github.client import GitHubClient, GitHubFailure, get_github_client

router = APIRouter(prefix="/v1/auth")


def cookie_options():
    return {"secure": get_settings().app_env == "production", "samesite": "lax", "path": "/"}


@router.get("/github/start")
def start(db: Session = Depends(get_db)):
    config = get_settings()
    if not config.github_oauth_enabled:
        raise HTTPException(503, "GitHub sign-in is not configured")
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    db.add(OAuthAttempt(state_hash=digest(state), verifier_ciphertext=cipher().encrypt(verifier.encode()).decode(),
                        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
    db.commit()
    params = {"client_id": config.github_client_id, "redirect_uri": config.github_callback_url,
              "state": state, "code_challenge": challenge, "code_challenge_method": "S256"}
    response = RedirectResponse("https://github.com/login/oauth/authorize?" + urlencode(params), 302,
                                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    response.set_cookie("rp_oauth", state, httponly=True, max_age=600, **cookie_options())
    return response


@router.get("/github/callback")
def callback(request: Request, code: str = Query(default="", max_length=4096),
             state: str = Query(default="", max_length=256), db: Session = Depends(get_db),
             github: GitHubClient = Depends(get_github_client)):
    config = get_settings()
    if not config.github_oauth_enabled:
        raise HTTPException(503, "GitHub sign-in is not configured")
    cookie = request.cookies.get("rp_oauth", "")
    import hmac
    if not code or not state or not cookie or not hmac.compare_digest(state.encode(), cookie.encode()):
        raise HTTPException(400, "Invalid authorization response")
    # Consume before external calls. DELETE RETURNING makes concurrent replay single-use.
    record = db.execute(delete(OAuthAttempt).where(
        OAuthAttempt.state_hash == digest(state),
        OAuthAttempt.expires_at > datetime.now(timezone.utc),
    ).returning(OAuthAttempt.verifier_ciphertext)).scalar_one_or_none()
    db.commit()
    if not record:
        raise HTTPException(400, "Invalid authorization response")
    try:
        verifier = cipher().decrypt(record.encode()).decode()
        result = github.exchange_code(code, verifier)
        token = result.get("access_token")
        if not isinstance(token, str) or not token:
            raise GitHubFailure("github_authorization_failed")
        user_data = github.current_user(token)
        github_id, login = user_data.get("id"), user_data.get("login")
        if (not isinstance(github_id, int) or isinstance(github_id, bool) or github_id <= 0
                or github_id >= 2**63 or not isinstance(login, str) or not 0 < len(login) <= 100):
            raise GitHubFailure("github_identity_invalid")
    except (GitHubFailure, InvalidToken, ValueError, UnicodeError):
        raise HTTPException(502, "GitHub sign-in failed") from None
    user = db.query(User).filter_by(github_user_id=github_id).one_or_none()
    if not user:
        user = User(github_user_id=github_id, login=login)
        db.add(user)
        db.flush()
    else:
        user.login = login
    personal = db.get(PersonalTenant, user.id)
    if personal is None:
        tenant = Tenant(name=f"GitHub user {github_id}")
        db.add(tenant)
        db.flush()
        db.add(Membership(user_id=user.id, tenant_id=tenant.id))
        db.flush()
        personal = PersonalTenant(user_id=user.id, tenant_id=tenant.id)
        db.add(personal)
        db.flush()
    # Rotate existing browser session without exposing any GitHub credential to the browser.
    old = request.cookies.get("rp_session")
    if old:
        existing = db.get(AuthSession, digest(old))
        if existing:
            existing.revoked_at = datetime.now(timezone.utc)
            existing.github_token_ciphertext = ""
    session_token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    expires = result.get("expires_in", 3600)
    if not isinstance(expires, int) or isinstance(expires, bool) or expires <= 0:
        raise HTTPException(502, "GitHub sign-in failed")
    age = min(expires, 3600)
    db.add(AuthSession(id_hash=digest(session_token), user_id=user.id, tenant_id=personal.tenant_id,
                       github_token_ciphertext=cipher().encrypt(token.encode()).decode(),
                       csrf_hash=digest(csrf), expires_at=datetime.now(timezone.utc) + timedelta(seconds=age)))
    db.commit()
    response = RedirectResponse(config.web_origin.rstrip("/") + "/", 303,
                                headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
    response.delete_cookie("rp_oauth", **cookie_options())
    response.set_cookie("rp_session", session_token, httponly=True, max_age=age, **cookie_options())
    response.set_cookie("rp_csrf", csrf, httponly=False, max_age=age, **cookie_options())
    return response


@router.get("/me")
def me(identity: Principal = Depends(principal), db: Session = Depends(get_db)):
    user = db.get(User, identity.user_id)
    return JSONResponse({"user": {"id": str(user.id), "login": user.login},
                         "tenant_id": str(identity.tenant_id), "demo": identity.demo},
                        headers={"Cache-Control": "no-store"})


@router.post("/logout")
def logout(request: Request, identity: Principal = Depends(principal), db: Session = Depends(get_db)):
    require_csrf(request, identity, db)
    row = db.get(AuthSession, identity.session_hash)
    row.revoked_at = datetime.now(timezone.utc)
    row.github_token_ciphertext = ""
    db.commit()
    response = JSONResponse({"status": "signed_out"}, headers={"Cache-Control": "no-store"})
    response.delete_cookie("rp_session", **cookie_options())
    response.delete_cookie("rp_csrf", **cookie_options())
    return response
