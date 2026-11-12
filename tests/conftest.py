import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def db_session():
    """A SQLAlchemy session against a fresh in-memory SQLite DB, wired as
    `client`'s `get_db` override too (same `StaticPool` connection, so
    anything committed here is visible to requests `client` makes) -- lets
    a test set up rows directly via the ORM (e.g. a `Token`, to simulate an
    already-connected household) before hitting an endpoint."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session):
    """TestClient wired to `db_session`'s fresh in-memory SQLite DB."""
    with TestClient(app) as test_client:
        yield test_client
