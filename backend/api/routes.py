"""API routes for script execution and management."""
import json
import time
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from models.schemas import (
    ExecuteRequest,
    ExecuteResponse,
    DockerStatusResponse,
    ExecutionsListResponse,
    ExecutionInfo
)
from services.docker_manager import DockerManager
from services.script_executor import ScriptExecutor
from services.script_storage import ScriptStorage

router = APIRouter()

# Initialize services
docker_manager = DockerManager()
script_executor = ScriptExecutor()
script_storage = ScriptStorage()


@router.post("/execute", response_model=ExecuteResponse)
async def execute_script(request: ExecuteRequest):
    """Start script execution.

    Returns execution_id and stream URL for SSE connection.
    """
    # Check if executor is busy
    if script_executor.is_busy():
        raise HTTPException(
            status_code=429,
            detail="Another execution is already running. Please wait for it to complete."
        )

    # Generate unique execution ID
    execution_id = f"exec_{int(time.time())}_{hash(request.script_name) % 10000:04d}"

    # Save script content to file
    from config import SCRIPTS_DIR
    script_path = SCRIPTS_DIR / f"{execution_id}.py"
    script_path.write_text(request.script_content)

    # Save initial metadata
    script_storage.save_metadata(
        execution_id=execution_id,
        script_name=request.script_name,
        project_name=request.project_name,
        started_at=datetime.utcnow().isoformat()
    )

    return ExecuteResponse(
        execution_id=execution_id,
        status="queued",
        stream_url=f"/api/execute/{execution_id}/stream"
    )


@router.get("/execute/{execution_id}/stream")
async def stream_execution(execution_id: str):
    """Stream execution logs via Server-Sent Events.

    This endpoint keeps the connection open and streams execution
    output in real-time using SSE format.
    """
    # Get execution metadata to retrieve script content
    metadata = script_storage.get_execution(execution_id)

    if not metadata:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Read script content
    from config import SCRIPTS_DIR
    script_path = SCRIPTS_DIR / f"{execution_id}.py"

    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script file not found")

    script_content = script_path.read_text()

    async def event_generator():
        """Generate SSE events from execution."""
        try:
            # Send start event
            yield f"data: {json.dumps({'type': 'started', 'execution_id': execution_id})}\n\n"

            # Check and start Docker containers if needed
            if not await docker_manager.all_running():
                yield f"data: {json.dumps({'type': 'docker_status', 'message': 'Starting Docker containers...'})}\n\n"

                result = await docker_manager.start_containers()

                if not result.get("success"):
                    error_msg = result.get("message", "Failed to start containers")
                    yield f"data: {json.dumps({'type': 'error', 'data': error_msg})}\n\n"
                    return

                yield f"data: {json.dumps({'type': 'docker_status', 'message': 'Docker containers ready'})}\n\n"

            # Execute script and stream output
            started_at = datetime.utcnow().isoformat()
            exit_code = None
            duration_seconds = None

            async for message in script_executor.execute_in_docker(execution_id, script_content):
                # Append to log file
                if message.get("type") in ["stdout", "stderr", "info"]:
                    script_storage.append_log(
                        execution_id,
                        f"[{message.get('timestamp', '')}] {message.get('data', '')}\n"
                    )

                # Check for completion
                if message.get("type") == "completed":
                    exit_code = message.get("exit_code")
                    duration_seconds = message.get("duration_seconds")

                # Stream to client
                yield f"data: {json.dumps(message)}\n\n"

            # Update metadata with final status
            script_storage.save_metadata(
                execution_id=execution_id,
                script_name=metadata["script_name"],
                project_name=metadata["project_name"],
                exit_code=exit_code,
                started_at=started_at,
                completed_at=datetime.utcnow().isoformat(),
                duration_seconds=duration_seconds
            )

        except Exception as e:
            error_data = {
                "type": "error",
                "data": f"Stream error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/docker/status", response_model=DockerStatusResponse)
async def get_docker_status():
    """Get Docker containers status."""
    status = await docker_manager.check_containers_status()
    return DockerStatusResponse(**status)


@router.post("/docker/start")
async def start_docker_containers():
    """Start Docker containers."""
    result = await docker_manager.start_containers()

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))

    return result


@router.get("/executions", response_model=ExecutionsListResponse)
async def list_executions(limit: int = 50, status: str = "all"):
    """List execution history.

    Args:
        limit: Maximum number of executions to return
        status: Filter by status (all|completed|failed|running)
    """
    executions = script_storage.get_executions(limit=limit, status=status)

    return ExecutionsListResponse(
        executions=[ExecutionInfo(**e) for e in executions],
        total=len(executions)
    )


@router.get("/executions/{execution_id}")
async def get_execution_details(execution_id: str):
    """Get execution details."""
    metadata = script_storage.get_execution(execution_id)

    if not metadata:
        raise HTTPException(status_code=404, detail="Execution not found")

    return metadata


@router.get("/executions/{execution_id}/logs")
async def get_execution_logs(execution_id: str):
    """Get full execution logs."""
    logs = script_storage.get_logs(execution_id)

    if logs is None:
        raise HTTPException(status_code=404, detail="Logs not found")

    return {"execution_id": execution_id, "logs": logs}


@router.delete("/executions/{execution_id}")
async def stop_execution(execution_id: str):
    """Stop a running execution."""
    success = await script_executor.stop_execution(execution_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Execution not found or not running"
        )

    return {"execution_id": execution_id, "status": "stopped"}
