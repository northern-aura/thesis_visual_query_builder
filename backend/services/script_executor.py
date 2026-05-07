"""Script execution service using Docker containers."""
import docker
import asyncio
import time
import re
from datetime import datetime
from typing import AsyncGenerator, Dict, Optional, List
from pathlib import Path
from config import SCRIPTS_DIR, EXECUTION_TIMEOUT


class ScriptExecutor:
    """Executes Python scripts inside Docker containers."""

    def __init__(self):
        """Initialize execution state."""
        self._client: Optional[docker.DockerClient] = None
        self.current_execution: Optional[str] = None  # Only one execution at a time

    def _get_client(self) -> docker.DockerClient:
        """Get or create Docker client lazily."""
        if self._client is None:
            try:
                self._client = docker.from_env()
            except Exception as e:
                raise RuntimeError(
                    f"Docker is not available. Please ensure Docker Desktop is running.\n"
                    f"Error: {str(e)}"
                )
        return self._client

    def is_busy(self) -> bool:
        """Check if an execution is currently running."""
        return self.current_execution is not None

    def _get_jobmanager_container(self):
        """Get the Flink jobmanager container."""
        client = self._get_client()
        return client.containers.get("jobmanager")

    def _list_running_job_ids(self, container) -> List[str]:
        """Return list of running Flink JobIDs from `flink list --running`."""
        try:
            res = container.exec_run(
                "flink list --running",
                stdout=True,
                stderr=True,
                demux=True
            )
            stdout, stderr = res.output if hasattr(res, "output") else (None, None)
            text = ""
            if stdout:
                text += stdout.decode("utf-8", errors="replace")
            if stderr:
                text += "\n" + stderr.decode("utf-8", errors="replace")

            # Flink JobIDs are 32-char hex strings.
            ids = re.findall(r"\b[a-f0-9]{32}\b", text)
            # Preserve order and uniqueness
            out = []
            seen = set()
            for jid in ids:
                if jid not in seen:
                    seen.add(jid)
                    out.append(jid)
            return out
        except Exception:
            return []

    def _cancel_running_jobs(self, container) -> List[str]:
        """Cancel all currently running Flink jobs, returning cancelled JobIDs."""
        job_ids = self._list_running_job_ids(container)
        cancelled = []
        for jid in job_ids:
            try:
                container.exec_run(
                    f"flink cancel {jid}",
                    stdout=True,
                    stderr=True,
                    demux=True
                )
                cancelled.append(jid)
            except Exception:
                # Best effort: keep going so one failed cancel doesn't block others.
                continue
        return cancelled

    async def execute_in_docker(
        self,
        execution_id: str,
        script_content: str
    ) -> AsyncGenerator[Dict, None]:
        """Execute script inside pyflink Docker container.

        Args:
            execution_id: Unique execution identifier
            script_content: Python script content to execute

        Yields:
            Dict messages with type, data, and timestamp
        """
        # Mark as busy
        self.current_execution = execution_id

        try:
            # Save script to shared volume location
            script_path = SCRIPTS_DIR / f"{execution_id}.py"
            script_path.write_text(script_content)

            yield {
                "type": "info",
                "data": f"Script saved to {script_path.name}",
                "timestamp": datetime.utcnow().isoformat()
            }

            # Get Docker client
            try:
                client = self._get_client()
            except RuntimeError as e:
                yield {
                    "type": "error",
                    "data": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                return

            # Get jobmanager container
            try:
                container = self._get_jobmanager_container()
            except docker.errors.NotFound:
                yield {
                    "type": "error",
                    "data": "jobmanager container not found. Please ensure Docker containers are running.",
                    "timestamp": datetime.utcnow().isoformat()
                }
                return

            # Ensure no stale running jobs consume slots from previous runs.
            stale = self._cancel_running_jobs(container)
            if stale:
                yield {
                    "type": "info",
                    "data": f"Cancelled {len(stale)} stale Flink job(s): {', '.join(stale)}",
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Execute script inside container
            yield {
                "type": "info",
                "data": "Starting script execution in Docker container...",
                "timestamp": datetime.utcnow().isoformat()
            }

            exec_id = container.exec_run(
                f"python /scripts/{execution_id}.py",
                stream=True,
                demux=True,
                stdin=False
            )

            # Stream output
            start_time = time.time()
            for stdout, stderr in exec_id.output:
                # Check timeout
                if time.time() - start_time > EXECUTION_TIMEOUT:
                    yield {
                        "type": "error",
                        "data": f"Execution timeout after {EXECUTION_TIMEOUT}s",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    break

                if stdout:
                    yield {
                        "type": "stdout",
                        "data": stdout.decode('utf-8', errors='replace'),
                        "timestamp": datetime.utcnow().isoformat()
                    }

                if stderr:
                    yield {
                        "type": "stderr",
                        "data": stderr.decode('utf-8', errors='replace'),
                        "timestamp": datetime.utcnow().isoformat()
                    }

                # Small delay to prevent overwhelming the stream
                await asyncio.sleep(0.01)

            # Get exit code
            try:
                exec_inspect = client.api.exec_inspect(exec_id.output.id)
                exit_code = exec_inspect.get("ExitCode", -1)
            except:
                exit_code = -1

            duration = time.time() - start_time

            yield {
                "type": "completed",
                "exit_code": exit_code,
                "duration_seconds": round(duration, 2),
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            yield {
                "type": "error",
                "data": f"Execution error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }

        finally:
            # Mark as not busy
            self.current_execution = None

    async def stop_execution(self, execution_id: str) -> bool:
        """Stop a running execution.

        Args:
            execution_id: Execution to stop

        Returns:
            True if stopped successfully
        """
        was_current = (self.current_execution == execution_id)
        if was_current:
            self.current_execution = None

        cancelled_any = False
        try:
            container = self._get_jobmanager_container()
            cancelled = self._cancel_running_jobs(container)
            cancelled_any = len(cancelled) > 0
        except Exception:
            cancelled_any = False

        return was_current or cancelled_any
