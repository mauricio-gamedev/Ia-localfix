import sqlite3
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, status

from app.config import Settings
from app.database import connect, fts_available, initialize
from app.inference import InferenceUnavailable, create_plan, generate_project_files
from app.schemas import (
    GenerateRequest, GenerateResponse, MemoryCreate, MemoryOut, PlanRequest,
    PlanResponse, ProjectCreate, ProjectOut,
)
from app.workspaces import create_workspace, make_slug, write_generated_files


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        config.workspace_root.mkdir(parents=True, exist_ok=True)
        initialize(config.database_path)
        yield

    application = FastAPI(
        title="Ia-localfix API",
        version="0.2.0",
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

    return application


app = create_app()
