"""Pydantic models for request/response schemas."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ExecuteRequest(BaseModel):
    """Request model for script execution."""
    script_name: str
    script_content: str
    project_name: str
    auto_start_docker: bool = True


class ExecuteResponse(BaseModel):
    """Response model for execution start."""
    execution_id: str
    status: str
    stream_url: str


class DockerStatusResponse(BaseModel):
    """Response model for Docker status."""
    docker_available: bool
    containers: dict


class ExecutionInfo(BaseModel):
    """Model for execution metadata."""
    execution_id: str
    script_name: str
    project_name: str
    status: str
    exit_code: Optional[int] = None
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None


class ExecutionsListResponse(BaseModel):
    """Response model for executions list."""
    executions: list[ExecutionInfo]
    total: int
