"""
tests/conftest.py

Session-level configuration that must run BEFORE any test module is imported.

Key concern: test_api.py creates a module-level TestClient(app) that connects
directly to app.database.engine.  If DATABASE_URL points at tracksense.db, every
test run pollutes the production database with fake venues/horses and triggers the
seed guard to clear real data on next restart.

Fix: override DATABASE_URL to an isolated test file before app.database is imported.
conftest.py is always loaded by pytest before test modules, so the env var is in
place when test_api.py does `from app.server import app`.
"""

import os
import pathlib
import pytest

# Must be set at module level (not inside a fixture) so it is in place
# before pytest imports test_api.py, which imports app.database at module level.
os.environ["DATABASE_URL"] = "sqlite:///./test_tracksense.db"


@pytest.fixture(scope="session", autouse=True)
def _isolate_test_db():
    """
    Ensure a fresh test DB at the start of every pytest session, then seed
    the minimal data that test_api.py expects to find (an 'admin' user for
    JWT-authenticated endpoints).
    """
    db_path = pathlib.Path("test_tracksense.db")
    if db_path.exists():
        db_path.unlink()

    # Import app modules only after the env var above has taken effect.
    from app.database import Base, engine, SessionLocal
    from app.models import User
    from app.auth import hash_password as get_password_hash

    Base.metadata.create_all(bind=engine)

    # Seed the admin user so JWT-authenticated tests pass on a clean DB.
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(username="admin").first():
            admin = User(
                username="admin",
                hashed_password=get_password_hash("tracksense"),
                role="admin",
                full_name="Admin",
                active=True,
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()

    yield
    # Leave the file in place so failures can be inspected; CI can clean it.
