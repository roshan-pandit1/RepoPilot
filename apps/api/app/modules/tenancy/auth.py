import hmac

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.models import Membership
from app.infra.database import get_db

bearer = HTTPBearer(auto_error=False)


def tenant_identity(
    credential: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> int:
    config = get_settings()
    if not config.demo_auth_enabled or config.app_env == "production":
        raise HTTPException(401, "Authentication required")
    if not credential or not hmac.compare_digest(
        credential.credentials.encode("utf-8"), config.demo_api_token.get_secret_value().encode("utf-8")
    ):
        raise HTTPException(401, "Authentication required")
    membership = db.get(Membership, (config.demo_tenant_id, config.demo_user_id))
    if not membership:
        raise HTTPException(403, "Tenant membership required")
    return membership.tenant_id
