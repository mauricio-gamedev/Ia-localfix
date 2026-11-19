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


def test_generate_writes_files_only_inside_workspace(tmp_path, monkeypatch):
    import app.main

    async def fake_generate(*_args):
        return [{"path": "src/main.py", "content": "print('hello')\n"}]

    monkeypatch.setattr(app.main, "generate_project_files", fake_generate)
    with make_client(tmp_path) as client:
        project = client.post("/v1/projects", json={"name": "Generator Test"}).json()
        response = client.post(
            "/v1/agent/generate",
            json={"project_id": project["id"], "request": "Create a tiny Python app"},
        )
    assert response.status_code == 200
    assert response.json()["files"][0]["path"] == "src/main.py"
    assert (tmp_path / "workspaces" / "generator-test" / "src" / "main.py").read_text() == "print('hello')\n"


def test_generate_rejects_path_traversal_and_writes_nothing(tmp_path, monkeypatch):
    import app.main

    async def fake_generate(*_args):
        return [{"path": "../outside.txt", "content": "unsafe"}]

    monkeypatch.setattr(app.main, "generate_project_files", fake_generate)
    with make_client(tmp_path) as client:
        project = client.post("/v1/projects", json={"name": "Traversal Test"}).json()
        response = client.post(
            "/v1/agent/generate",
            json={"project_id": project["id"], "request": "Create a tiny Python app"},
        )
    assert response.status_code == 422
    assert not (tmp_path / "workspaces" / "outside.txt").exists()


def test_generate_never_overwrites_existing_file(tmp_path, monkeypatch):
    import app.main

    async def fake_generate(*_args):
        return [{"path": "README.md", "content": "replace"}]

    monkeypatch.setattr(app.main, "generate_project_files", fake_generate)
    with make_client(tmp_path) as client:
        project = client.post("/v1/projects", json={"name": "No Overwrite"}).json()
        target = tmp_path / "workspaces" / "no-overwrite" / "README.md"
        target.write_text("original")
        response = client.post(
            "/v1/agent/generate",
            json={"project_id": project["id"], "request": "Create a tiny Python app"},
        )
    assert response.status_code == 409
    assert target.read_text() == "original"


def _agent_proposal(path="src/main.py", content="print('agent output')\\n"):
    return {
        "summary": "Create a minimal Python project.",
        "plan": "Create the entry point and validate its contents.",
        "steps": [
            {
                "title": "Create the entry point",
                "description": "Add the requested Python source file.",
            },
            {
                "title": "Review the generated output",
                "description": "Inspect the file before running any build or test tools.",
            },
        ],
        "files": [{"path": path, "content": content}],
    }


def test_agent_run_waits_for_approval_and_records_events(tmp_path, monkeypatch):
    import app.main

    async def fake_proposal(*_args):
        return _agent_proposal()

    monkeypatch.setattr(app.main, "generate_agent_proposal", fake_proposal)
    with make_client(tmp_path) as client:
        project = client.post("/v1/projects", json={"name": "Agent Workflow"}).json()
        response = client.post(
            "/v1/agent/runs",
            json={"project_id": project["id"], "request": "Create a minimal Python project"},
        )
        assert response.status_code == 201
        run = response.json()
        assert run["status"] == "awaiting_approval"
        assert run["files"][0]["path"] == "src/main.py"
        assert not (tmp_path / "workspaces" / "agent-workflow" / "src" / "main.py").exists()

        events = client.get(f"/v1/agent/runs/{run['id']}/events")
        assert events.status_code == 200
        assert [event["event_type"] for event in events.json()] == [
            "proposal_created",
            "awaiting_approval",
        ]


def test_agent_approval_applies_files_once(tmp_path, monkeypatch):
    import app.main

    async def fake_proposal(*_args):
        return _agent_proposal()

    monkeypatch.setattr(app.main, "generate_agent_proposal", fake_proposal)
    with make_client(tmp_path) as client:
        project = client.post("/v1/projects", json={"name": "Approved Agent"}).json()
        run = client.post(
            "/v1/agent/runs",
            json={"project_id": project["id"], "request": "Create a minimal Python project"},
        ).json()

        approved = client.post(f"/v1/agent/runs/{run['id']}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "completed"
        target = tmp_path / "workspaces" / "approved-agent" / "src" / "main.py"
        assert target.read_text() == "print('agent output')\\n"

        duplicate = client.post(f"/v1/agent/runs/{run['id']}/approve")
        assert duplicate.status_code == 409

        events = client.get(f"/v1/agent/runs/{run['id']}/events").json()
        assert events[-1]["event_type"] == "files_applied"


def test_agent_rejection_never_writes_files(tmp_path, monkeypatch):
    import app.main

    async def fake_proposal(*_args):
        return _agent_proposal()

    monkeypatch.setattr(app.main, "generate_agent_proposal", fake_proposal)
    with make_client(tmp_path) as client:
        project = client.post("/v1/projects", json={"name": "Rejected Agent"}).json()
        run = client.post(
            "/v1/agent/runs",
            json={"project_id": project["id"], "request": "Create a minimal Python project"},
        ).json()

        rejected = client.post(
            f"/v1/agent/runs/{run['id']}/reject",
            json={"reason": "Review requested changes first."},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"
        assert not (tmp_path / "workspaces" / "rejected-agent" / "src" / "main.py").exists()
        assert client.post(f"/v1/agent/runs/{run['id']}/approve").status_code == 409


def test_agent_rejects_path_traversal_before_persisting_run(tmp_path, monkeypatch):
    import app.main

    async def fake_proposal(*_args):
        return _agent_proposal(path="../outside.txt", content="unsafe")

    monkeypatch.setattr(app.main, "generate_agent_proposal", fake_proposal)
    with make_client(tmp_path) as client:
        project = client.post("/v1/projects", json={"name": "Unsafe Proposal"}).json()
        response = client.post(
            "/v1/agent/runs",
            json={"project_id": project["id"], "request": "Create a minimal Python project"},
        )
        assert response.status_code == 422
        assert client.get("/v1/agent/runs", params={"project_id": project["id"]}).json() == []
