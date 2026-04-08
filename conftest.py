import sys
import os

# Ensure the project root is on sys.path so `app` is importable
sys.path.insert(0, os.path.dirname(__file__))

# ------------------------------------------------------------------ #
# SQLite schema bootstrap
# For SQLite test runs: delete stale DB and recreate from ORM models
# so new columns/tables are always present without running Alembic.
# PostgreSQL (CI/prod) uses Alembic migrations instead.
# ------------------------------------------------------------------ #

_db_url = os.environ.get("DATABASE_URL", "")
if _db_url.startswith("sqlite:///"):
    _db_path = _db_url[len("sqlite:///"):]
    # Resolve relative path from project root
    if _db_path and not os.path.isabs(_db_path):
        _db_path = os.path.join(os.path.dirname(__file__), _db_path)
    if _db_path and os.path.exists(_db_path):
        os.remove(_db_path)

    # Import after env var is confirmed set so engine uses SQLite
    from app.database import Base, engine
    import app.models  # noqa: F401 — registers all ORM classes with Base

    Base.metadata.create_all(bind=engine)

    # Seed the default admin user so it occupies id=1, matching the
    # _mock_admin fixture in test_api.py (which hard-codes id=1).
    # Without this, test-created users get id=1 and conflict with the mock.
    from app.database import SessionLocal
    from app import crud
    db = SessionLocal()
    try:
        crud.create_user(db, "admin", "tracksense", "admin", "TrackSense Admin")
    except Exception:
        pass
    finally:
        db.close()
