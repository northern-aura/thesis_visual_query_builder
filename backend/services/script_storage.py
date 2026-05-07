"""Script and execution metadata storage service."""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
from config import SCRIPTS_DIR, MAX_EXECUTIONS_HISTORY


class ScriptStorage:
    """Manages storage of scripts, logs, and execution metadata."""

    def __init__(self):
        """Initialize storage directories."""
        self.scripts_dir = SCRIPTS_DIR
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

    def save_metadata(
        self,
        execution_id: str,
        script_name: str,
        project_name: str,
        exit_code: Optional[int] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        duration_seconds: Optional[float] = None
    ) -> None:
        """Save execution metadata to JSON file.

        Args:
            execution_id: Unique execution identifier
            script_name: Name of the script
            project_name: Project name
            exit_code: Script exit code
            started_at: ISO timestamp of start
            completed_at: ISO timestamp of completion
            duration_seconds: Execution duration
        """
        metadata = {
            "execution_id": execution_id,
            "script_name": script_name,
            "project_name": project_name,
            "status": "completed" if exit_code == 0 else "failed" if exit_code is not None else "running",
            "exit_code": exit_code,
            "started_at": started_at or datetime.utcnow().isoformat(),
            "completed_at": completed_at,
            "duration_seconds": duration_seconds
        }

        meta_path = self.scripts_dir / f"{execution_id}.json"
        meta_path.write_text(json.dumps(metadata, indent=2))

        # Auto-cleanup old executions
        self.cleanup_old_executions()

    def append_log(self, execution_id: str, log_data: str) -> None:
        """Append log data to execution log file.

        Args:
            execution_id: Unique execution identifier
            log_data: Log data to append
        """
        log_path = self.scripts_dir / f"{execution_id}.log"
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(log_data)

    def get_executions(self, limit: int = 50, status: str = "all") -> List[Dict]:
        """Get list of executions.

        Args:
            limit: Maximum number of executions to return
            status: Filter by status (all|completed|failed|running)

        Returns:
            List of execution metadata dicts
        """
        executions = []

        # Scan for metadata JSON files
        for meta_file in self.scripts_dir.glob("exec_*.json"):
            try:
                with open(meta_file, 'r') as f:
                    metadata = json.load(f)

                # Filter by status if specified
                if status != "all" and metadata.get("status") != status:
                    continue

                executions.append(metadata)
            except Exception as e:
                print(f"Error loading {meta_file}: {e}")
                continue

        # Sort by started_at (most recent first)
        executions.sort(
            key=lambda x: x.get("started_at", ""),
            reverse=True
        )

        return executions[:limit]

    def get_execution(self, execution_id: str) -> Optional[Dict]:
        """Get execution metadata by ID.

        Args:
            execution_id: Unique execution identifier

        Returns:
            Execution metadata dict or None if not found
        """
        meta_path = self.scripts_dir / f"{execution_id}.json"

        if not meta_path.exists():
            return None

        try:
            with open(meta_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading execution {execution_id}: {e}")
            return None

    def get_logs(self, execution_id: str) -> Optional[str]:
        """Get full execution logs.

        Args:
            execution_id: Unique execution identifier

        Returns:
            Log content as string or None if not found
        """
        log_path = self.scripts_dir / f"{execution_id}.log"

        if not log_path.exists():
            return None

        try:
            return log_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"Error reading logs for {execution_id}: {e}")
            return None

    def cleanup_old_executions(self) -> int:
        """Clean up old executions, keeping only the most recent ones.

        Returns:
            Number of executions deleted
        """
        # Get all metadata files
        meta_files = sorted(
            self.scripts_dir.glob("exec_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        if len(meta_files) <= MAX_EXECUTIONS_HISTORY:
            return 0

        # Delete oldest executions
        to_delete = meta_files[MAX_EXECUTIONS_HISTORY:]
        deleted = 0

        for meta_file in to_delete:
            execution_id = meta_file.stem

            # Delete all related files (.json, .py, .log)
            for suffix in ['.json', '.py', '.log']:
                file_path = self.scripts_dir / f"{execution_id}{suffix}"
                if file_path.exists():
                    try:
                        file_path.unlink()
                        deleted += 1
                    except Exception as e:
                        print(f"Error deleting {file_path}: {e}")

        return deleted // 3  # Return number of executions deleted (3 files per execution)
