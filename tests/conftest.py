import pytest
import os

# Use SQLite in-memory for tests
os.environ["DATABASE_URL"] = "sqlite:///./test_documind.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "true"
os.environ["AWS_ACCESS_KEY_ID"] = ""
os.environ["AWS_SECRET_ACCESS_KEY"] = ""
os.environ["S3_BUCKET"] = "test-bucket"
os.environ["FAISS_INDEX_DIR"] = "./test_faiss_indexes"

# Must import AFTER setting env vars to override cached settings
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.models.db import Base, get_db

TEST_DB_URL = "sqlite:///./test_documind.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create tables before all tests, teardown after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    import pathlib
    pathlib.Path("./test_documind.db").unlink(missing_ok=True)


@pytest.fixture(scope="function")
def client():
    """FastAPI test client with test DB override."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def registered_user(client):
    """Register a test user and return their credentials."""
    user_data = {"email": "testuser@example.com", "password": "TestPass123", "full_name": "Test User"}
    client.post("/api/v1/auth/register", json=user_data)
    return user_data


@pytest.fixture(scope="function")
def auth_headers(client, registered_user):
    """Return auth headers for a logged-in test user."""
    response = client.post("/api/v1/auth/login", json={
        "email": registered_user["email"],
        "password": registered_user["password"],
    })
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
