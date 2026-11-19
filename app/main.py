import json
import sqlite3
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, status

from app.agent import add_event, event_responses, run_response
from app.config import Settings
from app.database import connect, fts_available, initialize
from app.inference import (
    InferenceUnavailable,
    create_plan,
    generate_agent_proposal,
    generate_project_files,
)
from app.schemas import (
    AgentEventResponse,
    ProjectInspectionResponse,
    AgentRejectRequest,
    AgentRunCreate,
    AgentRunResponse,
    GenerateRequest,
    GenerateResponse,
    MemoryCreate,
    MemoryOut,
    PlanRequest,
    PlanResponse,
    ProjectCreate,
    ProjectOut,
    ProjectValidationResponse,
)
from app.validation import validate_project
from app.workspaces import (
    apply_generated_changes,
    create_workspace,
    inspect_workspace,
    make_slug,
    validate_generated_changes,
    validate_generated_files,
    write_generated_files,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        config.workspace_root.mkdir(parents=True, exist_ok=True)
        initialize(config.database_path)
        # Never replay an interrupted write automatically after a process restart.
        with connect(config.database_path) as db:
            interrupted = db.execute(
                "SELECT id FROM agent_runs WHERE status = 'applying'"
            ).fetchall()
            for item in interrupted:
                db.execute(
                    """UPDATE agent_runs SET status = 'failed',
                       error = 'Application was interrupted by a process restart; inspect workspace before retrying.',
                       updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (item["id"],),
                )
                add_event(
                    db,
                    item["id"],
                    "application_interrupted",
                    {"message": "Process restarted while files were being applied. Inspect the workspace before retrying."},
                )
        yield

    application = FastAPI(
        title="Ia-localfix API",
        version="0.4.0",
        description="Local-first AI software engineering control plane.",
        lifespan=lifespan,
    )
    application.state.settings = config

    @application.get("/health")
    async def health():
        return {"status": "ok", "service": "ia-localfix-api"}

    @application.get("/v1/projects", response_model=list[ProjectOut])
    async def list_projects():
        with connect(config.database_path) as db:
            rows = db.execute(
                "SELECT id, name, slug, created_at FROM projects ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    @application.post("/v1/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
    async def create_project(payload: ProjectCreate):
        try:
            slug = make_slug(payload.name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        project_id = str(uuid.uuid4())
        try:
            workspace = create_workspace(config.workspace_root, slug)
        except FileExistsError as exc:
            raise HTTPException(
                status_code=409, detail="A project with this name already exists."
            ) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(
                status_code=400, detail="Could not create a safe project workspace."
            ) from exc

        try:
            with connect(config.database_path) as db:
                db.execute(
                    "INSERT INTO projects (id, name, slug, workspace_path) VALUES (?, ?, ?, ?)",
                    (project_id, payload.name.strip(), slug, str(workspace)),
                )
                row = db.execute(
                    "SELECT id, name, slug, created_at FROM projects WHERE id = ?",
                    (project_id,),
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            workspace.rmdir()
            raise HTTPException(status_code=409, detail="Project already exists.") from exc
        return dict(row)

    @application.get(
        "/v1/projects/{project_id}/inspect",
        response_model=ProjectInspectionResponse,
    )
    async def inspect_project(project_id: str):
        with connect(config.database_path) as db:
            project = db.execute(
                "SELECT id, slug FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")
        try:
            snapshot = inspect_workspace(config.workspace_root, project["slug"])
        except (FileNotFoundError, ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        # Do not return full source contents from the inspection API.
        public_files = [
            {
                "path": item["path"],
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
                "preview": item["preview"],
                "truncated": item["truncated"],
            }
            for item in snapshot["files"]
        ]
        return {
            "project_id": project_id,
            "files": public_files,
            "file_count": snapshot["file_count"],
            "omitted_count": snapshot["omitted_count"],
            "total_bytes": snapshot["total_bytes"],
            "project_markers": snapshot["project_markers"],
        }

    @application.post(
        "/v1/projects/{project_id}/validate",
        response_model=ProjectValidationResponse,
    )
    async def validate_project_files(project_id: str):
        with connect(config.database_path) as db:
            project = db.execute(
                "SELECT id, slug FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")
        try:
            result = validate_project(config.workspace_root, project["slug"])
        except (FileNotFoundError, ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"project_id": project_id, **result}

    @application.post("/v1/memory", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
    async def save_memory(payload: MemoryCreate):
        memory_id = str(uuid.uuid4())
        with connect(config.database_path) as db:
            if payload.project_id:
                exists = db.execute(
                    "SELECT 1 FROM projects WHERE id = ?", (payload.project_id,)
                ).fetchone()
                if not exists:
                    raise HTTPException(status_code=404, detail="Project not found.")
            db.execute(
                "INSERT INTO memories (id, project_id, content) VALUES (?, ?, ?)",
                (memory_id, payload.project_id, payload.content.strip()),
            )
            if fts_available(db):
                db.execute(
                    "INSERT INTO memories_fts (memory_id, content) VALUES (?, ?)",
                    (memory_id, payload.content.strip()),
                )
            row = db.execute(
                "SELECT id, project_id, content, created_at FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        return dict(row)

    @application.get("/v1/memory", response_model=list[MemoryOut])
    async def search_memory(q: str = Query(default="", max_length=200)):
        with connect(config.database_path) as db:
            if q.strip() and fts_available(db):
                terms = [term.replace('"', '""') for term in q.split() if term]
                match = " AND ".join(f'"{term}"' for term in terms)
                rows = db.execute(
                    """SELECT m.id, m.project_id, m.content, m.created_at
                       FROM memories m JOIN memories_fts f ON f.memory_id = m.id
                       WHERE memories_fts MATCH ? ORDER BY m.created_at DESC LIMIT 100""",
                    (match,),
                ).fetchall() if match else []
            elif q.strip():
                rows = db.execute(
                    """SELECT id, project_id, content, created_at FROM memories
                       WHERE content LIKE ? ORDER BY created_at DESC LIMIT 100""",
                    (f"%{q}%",),
                ).fetchall()
            else:
                rows = db.execute(
                    """SELECT id, project_id, content, created_at FROM memories
                       ORDER BY created_at DESC LIMIT 100"""
                ).fetchall()
        return [dict(row) for row in rows]

    @application.post("/v1/agent/plan", response_model=PlanResponse)
    async def plan(payload: PlanRequest):
        if len(payload.request) > config.max_plan_chars:
            raise HTTPException(status_code=413, detail="Planning request is too large.")
        if payload.project_id:
            with connect(config.database_path) as db:
                exists = db.execute(
                    "SELECT 1 FROM projects WHERE id = ?", (payload.project_id,)
                ).fetchone()
            if not exists:
                raise HTTPException(status_code=404, detail="Project not found.")
        try:
            result = await create_plan(
                config.ollama_base_url, config.ollama_model, payload.request
            )
        except InferenceUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"model": config.ollama_model, "plan": result}

    @application.post("/v1/agent/generate", response_model=GenerateResponse)
    async def generate(payload: GenerateRequest):
        with connect(config.database_path) as db:
            project = db.execute(
                "SELECT id, slug FROM projects WHERE id = ?", (payload.project_id,)
            ).fetchone()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found.")
        try:
            generated = await generate_project_files(
                config.ollama_base_url, config.ollama_model, payload.request
            )
            written = write_generated_files(
                config.workspace_root, project["slug"], generated
            )
        except InferenceUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "model": config.ollama_model,
            "project_id": payload.project_id,
            "files": written,
        }

    @application.post(
        "/v1/agent/runs",
        response_model=AgentRunResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_agent_run(payload: AgentRunCreate):
        with connect(config.database_path) as db:
            project = db.execute(
                "SELECT id, name, slug FROM projects WHERE id = ?",
                (payload.project_id,),
            ).fetchone()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found.")
            memories = db.execute(
                """SELECT content FROM memories
                   WHERE project_id = ? ORDER BY created_at DESC LIMIT 8""",
                (payload.project_id,),
            ).fetchall()

        try:
            snapshot = inspect_workspace(config.workspace_root, project["slug"])
        except (FileNotFoundError, ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        project_context = {
            "project_name": project["name"],
            "recent_project_memory": [row["content"] for row in memories],
            "project_markers": snapshot["project_markers"],
            "existing_files": [
                {
                    "path": item["path"],
                    "content": item["content"],
                    "sha256": item["sha256"],
                }
                for item in snapshot["files"]
            ],
            "generation_policy": (
                "Create missing files or update inspected text files only. "
                "Updates must use the provided exact SHA-256 fingerprint. Never delete files."
            ),
        }
        try:
            proposal = await generate_agent_proposal(
                config.ollama_base_url,
                config.ollama_model,
                payload.request,
                project_context,
            )
            validate_generated_changes(
                config.workspace_root, project["slug"], proposal["files"]
            )
        except InferenceUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        run_id = str(uuid.uuid4())
        with connect(config.database_path) as db:
            db.execute(
                """INSERT INTO agent_runs
                   (id, project_id, request, model, status, proposal_json)
                   VALUES (?, ?, ?, ?, 'awaiting_approval', ?)""",
                (
                    run_id,
                    payload.project_id,
                    payload.request,
                    config.ollama_model,
                    json.dumps(proposal, ensure_ascii=False),
                ),
            )
            add_event(
                db,
                run_id,
                "proposal_created",
                {
                    "summary": proposal["summary"],
                    "step_count": len(proposal["steps"]),
                    "file_count": len(proposal["files"]),
                },
            )
            add_event(
                db,
                run_id,
                "awaiting_approval",
                {"message": "No project files have been written yet."},
            )
            row = db.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return run_response(row)

    @application.get("/v1/agent/runs", response_model=list[AgentRunResponse])
    async def list_agent_runs(
        project_id: str = Query(min_length=1),
    ):
        with connect(config.database_path) as db:
            project = db.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found.")
            rows = db.execute(
                """SELECT * FROM agent_runs
                   WHERE project_id = ? ORDER BY created_at DESC LIMIT 50""",
                (project_id,),
            ).fetchall()
        return [run_response(row) for row in rows]

    @application.get("/v1/agent/runs/{run_id}", response_model=AgentRunResponse)
    async def get_agent_run(run_id: str):
        with connect(config.database_path) as db:
            row = db.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent run not found.")
        return run_response(row)

    @application.get(
        "/v1/agent/runs/{run_id}/events",
        response_model=list[AgentEventResponse],
    )
    async def get_agent_run_events(run_id: str):
        with connect(config.database_path) as db:
            exists = db.execute(
                "SELECT 1 FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if not exists:
                raise HTTPException(status_code=404, detail="Agent run not found.")
            return event_responses(db, run_id)

    @application.post(
        "/v1/agent/runs/{run_id}/approve",
        response_model=AgentRunResponse,
    )
    async def approve_agent_run(run_id: str):
        # Claim the run in one transaction so concurrent approval calls cannot
        # apply the same proposal twice.
        with connect(config.database_path) as db:
            row = db.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Agent run not found.")
            claimed = db.execute(
                """UPDATE agent_runs
                   SET status = 'applying', updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND status = 'awaiting_approval'""",
                (run_id,),
            )
            if claimed.rowcount != 1:
                raise HTTPException(
                    status_code=409,
                    detail=f"Agent run cannot be approved from status '{row['status']}'.",
                )
            project = db.execute(
                "SELECT slug FROM projects WHERE id = ?", (row["project_id"],)
            ).fetchone()
            proposal = json.loads(row["proposal_json"])
            add_event(db, run_id, "approval_granted", {"message": "User approved file application."})

        try:
            written = apply_generated_changes(
                config.workspace_root, project["slug"], proposal["files"]
            )
        except (FileExistsError, ValueError, OSError) as exc:
            with connect(config.database_path) as db:
                db.execute(
                    """UPDATE agent_runs SET status = 'failed', error = ?,
                       updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
                    (str(exc)[:1000], run_id),
                )
                add_event(
                    db,
                    run_id,
                    "application_failed",
                    {"error": str(exc)[:1000]},
                )
            if isinstance(exc, FileExistsError):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        with connect(config.database_path) as db:
            db.execute(
                """UPDATE agent_runs
                   SET status = 'completed', error = NULL,
                       updated_at = CURRENT_TIMESTAMP,
                       completed_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND status = 'applying'""",
                (run_id,),
            )
            add_event(
                db,
                run_id,
                "files_applied",
                {"files": written, "count": len(written)},
            )
            row = db.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return run_response(row)

    @application.post(
        "/v1/agent/runs/{run_id}/reject",
        response_model=AgentRunResponse,
    )
    async def reject_agent_run(run_id: str, payload: AgentRejectRequest):
        with connect(config.database_path) as db:
            row = db.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Agent run not found.")
            updated = db.execute(
                """UPDATE agent_runs
                   SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND status = 'awaiting_approval'""",
                (run_id,),
            )
            if updated.rowcount != 1:
                raise HTTPException(
                    status_code=409,
                    detail=f"Agent run cannot be rejected from status '{row['status']}'.",
                )
            add_event(db, run_id, "proposal_rejected", {"reason": payload.reason})
            result = db.execute(
                "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
            ).fetchone()
        return run_response(result)

    return application


app = create_app()
