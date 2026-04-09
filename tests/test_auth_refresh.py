"""
tests/test_auth_refresh.py

Tests for ITEM 3: JWT refresh always issues a 24h-from-now token.
"""

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.auth import create_access_token, decode_token


def test_refresh_token_expires_24h_from_call_time():
    """
    A token created via create_access_token should expire ~24h from NOW,
    regardless of when the original token was issued.
    """
    before = datetime.now(timezone.utc)
    token = create_access_token({"sub": "testuser"})
    after = datetime.now(timezone.utc)

    payload = decode_token(token)
    assert payload is not None

    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    expected_min = before + timedelta(hours=23, minutes=59)
    expected_max = after + timedelta(hours=24, minutes=1)

    assert exp >= expected_min, f"Expiry {exp} < expected min {expected_min}"
    assert exp <= expected_max, f"Expiry {exp} > expected max {expected_max}"


def test_refresh_at_t23h_gives_24h_not_1h():
    """
    A user refreshing at T+23h should get a new token that expires at T+47h
    (i.e., 24h from the refresh time), not T+24h (1h from now).

    We simulate this by controlling datetime.now() to be 23 hours in the future.
    """
    future_now = datetime.now(timezone.utc) + timedelta(hours=23)

    with patch("app.auth.datetime") as mock_dt:
        mock_dt.now.return_value = future_now

        token = create_access_token({"sub": "testuser"})

    payload = decode_token(token)
    assert payload is not None

    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    # Should be ~24h after the future_now, not just 1h from original issue
    expected = future_now + timedelta(hours=24)

    delta = abs((exp - expected).total_seconds())
    assert delta < 60, f"Expiry delta {delta}s too large — not issuing 24h from refresh time"


def test_refresh_endpoint_issues_new_token(tmp_path):
    """
    Smoke-test: hitting POST /auth/refresh returns a new access_token.
    Uses an existing valid token and verifies a new token is returned.
    """
    from fastapi.testclient import TestClient
    from app.server import app
    from app.database import get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.database import Base
    from app import crud

    # Minimal in-memory DB with one user
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    crud.create_user(session, "refreshtest", "password123", "viewer")

    app.dependency_overrides[get_db] = lambda: session

    token = create_access_token({"sub": "refreshtest"})
    with TestClient(app, raise_server_exceptions=True) as c:
        r = c.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    # New token must be different from the original
    assert body["access_token"] != token

    session.close()
    app.dependency_overrides.pop(get_db, None)
