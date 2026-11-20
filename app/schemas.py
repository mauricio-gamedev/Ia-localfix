from typing import Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class ProjectOut(BaseModel):
    id: str
    name: str
    slug: str
    created_at: str


class ProjectFilePreview(BaseModel):
    path: str
    size_bytes: int
    sha256: str
    preview: str
    truncated: bool


class ProjectInspectionResponse(BaseModel):
    project_id: str
    files: list[ProjectFilePreview]
    file_count: int
    omitted_count: int
    total_bytes: int
    project_markers: list[str]


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


class GenerateRequest(BaseModel):
    request: str = Field(min_length=5, max_length=12_000)
    project_id: str


class GeneratedFile(BaseModel):
    path: str
    size_bytes: int


class GenerateResponse(BaseModel):
    model: str
    project_id: str
    files: list[GeneratedFile]


class AgentRunCreate(BaseModel):
    request: str = Field(min_length=5, max_length=12_000)
    project_id: str


class AgentStep(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1_000)


class AgentProposedFile(BaseModel):
    path: str = Field(min_length=1, max_length=240)
    content: str = Field(max_length=1_000_000)
    operation: Literal["create", "update"] = "create"
    expected_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )


class AgentProposal(BaseModel):
    summary: str = Field(min_length=1, max_length=1_000)
    plan: str = Field(min_length=1, max_length=8_000)
    steps: list[AgentStep] = Field(min_length=1, max_length=12)
    files: list[AgentProposedFile] = Field(min_length=1, max_length=30)


class AgentFilePreview(BaseModel):
    path: str
    operation: Literal["create", "update"]
    expected_sha256: str | None
    size_bytes: int
    preview: str


class AgentRunResponse(BaseModel):
    id: str
    project_id: str
    status: str
    model: str
    request: str
    summary: str
    plan: str
    steps: list[AgentStep]
    files: list[AgentFilePreview]
    error: str | None
    created_at: str
    updated_at: str
    completed_at: str | None


class AgentRejectRequest(BaseModel):
    reason: str = Field(default="Rejected by user.", min_length=1, max_length=500)


class AgentEventResponse(BaseModel):
    id: str
    event_type: str
    payload: dict
    created_at: str


class ProjectValidationDiagnostic(BaseModel):
    path: str
    severity: Literal["error", "warning"]
    message: str
    line: int | None
    column: int | None


class ProjectValidationResponse(BaseModel):
    success: bool
    project_id: str
    checked_files: int
    error_count: int
    diagnostics: list[ProjectValidationDiagnostic]
    omitted_count: int
    project_markers: list[str]
    execution_performed: bool


class AgentRepairRequest(BaseModel):
    instructions: str | None = Field(default=None, max_length=4_000)


class BuildProfileResponse(BaseModel):
    id: str
    title: str
    description: str
    command_preview: str
    requires: str
    available: bool
    reason: str | None


class BuildJobCreate(BaseModel):
    profile_id: Literal[
        "python-unittest",
        "node-test",
        "android-debug",
        "android-unit-tests",
    ]
    parent_build_id: str | None = Field(default=None, min_length=1, max_length=64)


class BuildJobResponse(BaseModel):
    id: str
    project_id: str
    profile_id: str
    cycle_id: str
    iteration: int
    parent_build_id: str | None
    status: Literal[
        "awaiting_approval", "running", "succeeded", "failed", "timed_out", "rejected"
    ]
    result: dict | None
    error: str | None
    created_at: str
    updated_at: str
    started_at: str | None
    completed_at: str | None


class BuildEventResponse(BaseModel):
    id: str
    event_type: str
    payload: dict
    created_at: str
