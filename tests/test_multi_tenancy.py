"""
tests/test_multi_tenancy.py

Tests for ITEM 5: Multi-tenancy — Tenant table, tenant_id FK, /tenants endpoints,
JWT payload, and tenant-scoped filtering.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.server import app
from app.gate_registry import registry
from app.race_tracker import set_tracker
from app.routes import get_current_user
from app.database import get_db, Base
from app.models import User, Tenant, Horse
from app import crud


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_user(username, role, tenant_id=None):
    u = User()
    u.id = hash(username) % 100000
    u.username = username
    u.hashed_password = "x"
    u.role = role
    u.full_name = username
    u.active = True
    u.tenant_id = tenant_id
    return u


_super_admin = _make_user("super_admin", "admin", tenant_id=None)
_tenant_admin = _make_user("tenant_admin", "admin", tenant_id="TENANT-A")


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def super_admin_client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = lambda: _super_admin
    app.dependency_overrides[get_db] = override_db
    registry._venues.clear()
    set_tracker(None)

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, db_session

    registry._venues.clear()
    set_tracker(None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def tenant_admin_client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = lambda: _tenant_admin
    app.dependency_overrides[get_db] = override_db
    registry._venues.clear()
    set_tracker(None)

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, db_session

    registry._venues.clear()
    set_tracker(None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ------------------------------------------------------------------ #
# Tenant CRUD
# ------------------------------------------------------------------ #

def test_create_and_get_tenant(db_session):
    tenant = crud.create_tenant(db_session, name="Racing Victoria", slug="racing-vic")
    assert tenant.id is not None
    assert tenant.slug == "racing-vic"

    fetched = crud.get_tenant(db_session, tenant.id)
    assert fetched is not None
    assert fetched.name == "Racing Victoria"


def test_get_tenant_by_slug(db_session):
    crud.create_tenant(db_session, name="BHA", slug="bha")
    tenant = crud.get_tenant_by_slug(db_session, "bha")
    assert tenant is not None
    assert tenant.name == "BHA"


def test_list_tenants(db_session):
    crud.create_tenant(db_session, name="Tenant A", slug="tenant-a")
    crud.create_tenant(db_session, name="Tenant B", slug="tenant-b")
    tenants = crud.list_tenants(db_session)
    assert len(tenants) == 2


def test_delete_tenant(db_session):
    t = crud.create_tenant(db_session, name="Delete Me", slug="delete-me")
    deleted = crud.delete_tenant(db_session, t.id)
    assert deleted is True
    assert crud.get_tenant(db_session, t.id) is None


def test_delete_nonexistent_tenant_returns_false(db_session):
    assert crud.delete_tenant(db_session, "nonexistent-id") is False


# ------------------------------------------------------------------ #
# /tenants endpoints — super-admin access
# ------------------------------------------------------------------ #

def test_super_admin_can_list_tenants(super_admin_client):
    c, db = super_admin_client
    r = c.get("/tenants")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_super_admin_can_create_tenant(super_admin_client):
    c, db = super_admin_client
    r = c.post("/tenants", json={"name": "Test Org", "slug": "test-org"})
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "test-org"
    assert body["id"] is not None


def test_duplicate_slug_returns_409(super_admin_client):
    c, db = super_admin_client
    c.post("/tenants", json={"name": "First", "slug": "dup-slug"})
    r = c.post("/tenants", json={"name": "Second", "slug": "dup-slug"})
    assert r.status_code == 409


def test_super_admin_can_get_tenant(super_admin_client):
    c, db = super_admin_client
    created = c.post("/tenants", json={"name": "Get Me", "slug": "get-me"}).json()
    r = c.get(f"/tenants/{created['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "Get Me"


def test_get_unknown_tenant_returns_404(super_admin_client):
    c, _ = super_admin_client
    r = c.get("/tenants/no-such-tenant-id")
    assert r.status_code == 404


def test_super_admin_can_delete_tenant(super_admin_client):
    c, db = super_admin_client
    created = c.post("/tenants", json={"name": "Bye", "slug": "bye-tenant"}).json()
    r = c.delete(f"/tenants/{created['id']}")
    assert r.status_code == 204


def test_tenant_admin_cannot_access_tenants_endpoints(tenant_admin_client):
    """A user with tenant_id set is NOT a super-admin — must be denied."""
    c, _ = tenant_admin_client
    r = c.get("/tenants")
    assert r.status_code == 403


# ------------------------------------------------------------------ #
# Tenant filtering on list endpoints
# ------------------------------------------------------------------ #

def test_list_horses_filters_by_tenant(db_session):
    """Horses with different tenant_ids are filtered correctly."""
    # Create two tenants
    t_a = crud.create_tenant(db_session, name="Tenant A", slug="ta")
    t_b = crud.create_tenant(db_session, name="Tenant B", slug="tb")

    # Add horses to different tenants
    horse_a = Horse()
    horse_a.epc = "EPC-A1"
    horse_a.name = "Alpha"
    horse_a.tenant_id = t_a.id
    db_session.add(horse_a)

    horse_b = Horse()
    horse_b.epc = "EPC-B1"
    horse_b.name = "Beta"
    horse_b.tenant_id = t_b.id
    db_session.add(horse_b)

    horse_null = Horse()
    horse_null.epc = "EPC-NULL"
    horse_null.name = "Unscoped"
    horse_null.tenant_id = None
    db_session.add(horse_null)

    db_session.commit()

    # tenant A sees only A
    horses_a = crud.list_horses(db_session, tenant_id=t_a.id)
    assert len(horses_a) == 1
    assert horses_a[0].epc == "EPC-A1"

    # tenant B sees only B
    horses_b = crud.list_horses(db_session, tenant_id=t_b.id)
    assert len(horses_b) == 1
    assert horses_b[0].epc == "EPC-B1"

    # super-admin (tenant_id=None) sees all
    all_horses = crud.list_horses(db_session, tenant_id=None)
    assert len(all_horses) == 3


def test_list_users_filters_by_tenant(db_session):
    """list_users with tenant_id only returns matching users."""
    t = crud.create_tenant(db_session, name="Scoped Org", slug="scoped-org")

    u1 = crud.create_user(db_session, "user_scoped", "password1", "viewer")
    u1.tenant_id = t.id
    db_session.commit()

    u2 = crud.create_user(db_session, "user_unscoped", "password2", "viewer")
    # tenant_id remains None

    scoped = crud.list_users(db_session, tenant_id=t.id)
    assert len(scoped) == 1
    assert scoped[0].username == "user_scoped"

    all_users = crud.list_users(db_session, tenant_id=None)
    assert len(all_users) == 2


def test_list_webhooks_filters_by_tenant(db_session):
    """list_webhooks with tenant_id only returns matching subscriptions."""
    from app.models import WebhookSubscription
    from datetime import datetime, timezone

    t = crud.create_tenant(db_session, name="Webhook Org", slug="webhook-org")

    sub_a = WebhookSubscription(
        name="Sub A", url="https://a.example.com/hook", secret="s1",
        event_type="race.finished", active=True,
        created_at=datetime.now(timezone.utc), tenant_id=t.id,
    )
    sub_null = WebhookSubscription(
        name="Sub Null", url="https://null.example.com/hook", secret="s2",
        event_type="race.finished", active=True,
        created_at=datetime.now(timezone.utc), tenant_id=None,
    )
    db_session.add_all([sub_a, sub_null])
    db_session.commit()

    scoped = crud.list_webhooks(db_session, tenant_id=t.id)
    assert len(scoped) == 1
    assert scoped[0].name == "Sub A"

    all_subs = crud.list_webhooks(db_session, tenant_id=None)
    assert len(all_subs) == 2


# ------------------------------------------------------------------ #
# JWT payload includes tenant_id
# ------------------------------------------------------------------ #

def test_jwt_login_includes_tenant_id(super_admin_client):
    """/auth/login response includes tenant_id field."""
    c, db = super_admin_client
    # The super-admin mock has tenant_id=None; the login endpoint is overridden
    # by the test client auth override, so we just check the response shape
    # by testing the route directly returns tenant_id key.
    # (We test the login independently here via a real user in the DB)
    user = crud.create_user(db, "jwt_test_user", "password123", "viewer")
    user.tenant_id = None
    db.commit()

    # Remove auth override temporarily to test real login
    app.dependency_overrides.pop(get_current_user, None)
    r = c.post("/auth/login", json={"username": "jwt_test_user", "password": "password123"})
    app.dependency_overrides[get_current_user] = lambda: _super_admin

    assert r.status_code == 200
    body = r.json()
    assert "tenant_id" in body
