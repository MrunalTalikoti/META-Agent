"""
HTTP integration tests — hit FastAPI endpoints via httpx.AsyncClient.
Uses SQLite in-memory so no Docker/Postgres required.

Run with:
    pytest tests/integration/test_api.py -v
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import get_db
from app.models.database import Base


# ── In-memory SQLite DB fixture ───────────────────────────────────────────────

SQLITE_URL = "sqlite://"  # in-memory, per-test-session

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def override_db(db):
    app.dependency_overrides[get_db] = lambda: db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# ── Helper ────────────────────────────────────────────────────────────────────

async def _register_and_login(client: AsyncClient, email: str = "test@example.com") -> str:
    await client.post("/api/auth/register", json={"email": email, "password": "testpass123"})
    resp = await client.post(
        "/api/auth/token",
        data={"username": email, "password": "testpass123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return resp.json()["access_token"]


# ── Auth ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "newuser@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    assert resp.json()["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "pass"}
    await client.post("/api/auth/register", json=payload)
    resp = await client.post("/api/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/auth/register", json={"email": "login@example.com", "password": "pw"})
    resp = await client.post(
        "/api/auth/token",
        data={"username": "login@example.com", "password": "pw"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={"email": "wp@example.com", "password": "right"})
    resp = await client.post(
        "/api/auth/token",
        data={"username": "wp@example.com", "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


# ── Projects ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_project(client):
    token = await _register_and_login(client, "proj@example.com")
    resp = await client.post(
        "/api/projects/",
        json={"name": "My Project", "description": "Test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "My Project"


@pytest.mark.asyncio
async def test_list_projects_pagination(client):
    token = await _register_and_login(client, "listproj@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    for i in range(5):
        await client.post("/api/projects/", json={"name": f"P{i}"}, headers=headers)

    resp = await client.get("/api/projects/?page=1&limit=3", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    resp2 = await client.get("/api/projects/?page=2&limit=3", headers=headers)
    assert resp2.status_code == 200
    assert len(resp2.json()) == 2


@pytest.mark.asyncio
async def test_get_project_not_found(client):
    token = await _register_and_login(client, "notfound@example.com")
    resp = await client.get(
        "/api/projects/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project(client):
    token = await _register_and_login(client, "del@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    create = await client.post("/api/projects/", json={"name": "ToDelete"}, headers=headers)
    pid = create.json()["id"]

    resp = await client.delete(f"/api/projects/{pid}", headers=headers)
    assert resp.status_code == 204

    resp2 = await client.get(f"/api/projects/{pid}", headers=headers)
    assert resp2.status_code == 404


# ── Conversations ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_conversations_pagination(client):
    token = await _register_and_login(client, "convpag@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post("/api/projects/", json={"name": "CP"}, headers=headers)
    pid = proj.json()["id"]

    resp = await client.get(
        f"/api/conversations/?project_id={pid}&page=1&limit=10",
        headers=headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_get_conversation_not_found(client):
    token = await _register_and_login(client, "convnf@example.com")
    resp = await client.get(
        "/api/conversations/99999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── Metrics ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics(client):
    token = await _register_and_login(client, "metrics@example.com")
    resp = await client.get(
        "/api/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "projects" in data
    assert "tasks" in data
    assert "llm_usage" in data


# ── Health ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert "status" in resp.json()


@pytest.mark.asyncio
async def test_unauthenticated_request(client):
    resp = await client.get("/api/projects/")
    assert resp.status_code == 401
