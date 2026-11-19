from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ProjectOut(BaseModel):
    id: str
    name: str
    slug: str
    created_at: str


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    project_id: str | None = None


class MemoryOut(BaseModel):
    id: str
    project_id: str | None
    content: str
    created_at: str


class PlanRequest(BaseModel):
    request: str = Field(min_length=5, max_length=12_000)
    project_id: str | None = None


class PlanResponse(BaseModel):
    model: str
    plan: str
