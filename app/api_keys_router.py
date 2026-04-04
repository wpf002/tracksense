"""
api_keys_router.py

Admin-only API key management + shared auth dependency for third-party endpoints.

Keys are never stored in plaintext. On creation the raw key is returned once;
only a SHA-256 hash is persisted.  On every request the incoming key is hashed
and looked up in the database.
"""

import hashlib
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApiKey, User
from app import crud
from app.auth import decode_token

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

_security = HTTPBearer()


# ------------------------------------------------------------------ #
# Internal helpers
# ------------------------------------------------------------------ #

def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_key_by_hash(db: Session, raw: str) -> Optional[ApiKey]:
    return db.query(ApiKey).filter_by(key_hash=_hash_key(raw)).first()


# ------------------------------------------------------------------ #
# JWT dependency (local copy to avoid circular import with routes.py)
# ------------------------------------------------------------------ #

def _get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = crud.get_user_by_username(db, username)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


# ------------------------------------------------------------------ #
# Standalone get_api_key dependency (importable by other modules)
# ------------------------------------------------------------------ #

def get_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Validate X-API-Key header; raises 401 on failure."""
    api_key = _get_key_by_hash(db, x_api_key)
    if not api_key or not api_key.is_active:
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")
    return api_key


# ------------------------------------------------------------------ #
# Combined dependency: JWT *or* API key
# Used by read-only endpoints exposed to third-party integrations.
# ------------------------------------------------------------------ #

def require_jwt_or_api_key(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """
    Accept a request authenticated via either:
      - Authorization: Bearer <jwt>
      - X-API-Key: <raw-key>

    Raises 401 if neither credential is present or valid.
    """
    x_api_key = request.headers.get("X-API-Key")
    if x_api_key is not None:
        api_key = _get_key_by_hash(db, x_api_key)
        if api_key and api_key.is_active:
            return
        raise HTTPException(status_code=401, detail="Invalid or inactive API key")

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            username = payload.get("sub")
            if username:
                user = crud.get_user_by_username(db, username)
                if user and user.active:
                    return
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    raise HTTPException(
        status_code=401,
        detail="Authentication required: provide Authorization header or X-API-Key",
    )


# ------------------------------------------------------------------ #
# Admin guard
# ------------------------------------------------------------------ #

def _require_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


# ------------------------------------------------------------------ #
# Request models
# ------------------------------------------------------------------ #

class CreateApiKeyRequest(BaseModel):
    name: str


# ------------------------------------------------------------------ #
# Routes
# ------------------------------------------------------------------ #

@router.post("")
def create_api_key(
    req: CreateApiKeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user),
):
    _require_admin(current_user)
    raw_key = secrets.token_urlsafe(32)
    key_id = str(uuid.uuid4())
    api_key = ApiKey(
        id=key_id,
        key_hash=_hash_key(raw_key),
        name=req.name,
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": raw_key,   # returned once only — never stored in plaintext
        "created_at": api_key.created_at.isoformat() if api_key.created_at else None,
    }


@router.get("")
def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user),
):
    _require_admin(current_user)
    keys = db.query(ApiKey).order_by(ApiKey.created_at).all()
    return [
        {
            "id": k.id,
            "name": k.name,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "is_active": k.is_active,
        }
        for k in keys
    ]


@router.delete("/{key_id}")
def deactivate_api_key(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user),
):
    _require_admin(current_user)
    api_key = db.get(ApiKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail=f"API key '{key_id}' not found")
    api_key.is_active = False
    db.commit()
    return {"ok": True, "id": key_id, "is_active": False}
