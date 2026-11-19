from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=tmp_path / "db" / "test.sqlite3",
        workspace_root=tmp_path / "workspaces",
        ollama_base_url="http://127.0.0.1:9",
        ollama_model="test-model",
    )
    return TestClient(create_app(settings))


def test_health(tmp_path):
    with make_client(tmp_path) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_list_project(tmp_path):
    with make_client(tmp_path) as client:
        created = client.post("/v1/projects", json={"name": "My Android App"})
        assert created.status_code == 201
        project = created.json()
        assert project["slug"] == "my-android-app"
        assert (tmp_path / "workspaces" / "my-android-app").is_dir()

        listed = client.get("/v1/projects")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == project["id"]


def test_duplicate_project_is_conflict(tmp_path):
    with make_client(tmp_path) as client:
        assert client.post("/v1/projects", json={"name": "Demo App"}).status_code == 201
        response = client.post("/v1/projects", json={"name": "Demo App"})
    assert response.status_code == 409


def test_memory_create_and_search(tmp_path):
    with make_client(tmp_path) as client:
        saved = client.post("/v1/memory", json={"content": "Use Kotlin and Jetpack Compose"})
        assert saved.status_code == 201
        response = client.get("/v1/memory", params={"q": "Kotlin"})
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert "Kotlin" in response.json()[0]["content"]


def test_memory_rejects_unknown_project(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/v1/memory",
            json={"content": "orphan note", "project_id": "missing-project"},
        )
    assert response.status_code == 404


def test_plan_returns_service_unavailable_without_runtime(tmp_path):
    with make_client(tmp_path) as client:
        response = client.post(
            "/v1/agent/plan",
            json={"request": "Create a small Android application"},
        )
    assert response.status_code == 503
