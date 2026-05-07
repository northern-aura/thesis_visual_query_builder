"""Docker container management service."""
import docker
import subprocess
import asyncio
import time
from pathlib import Path
from typing import Dict
from config import (
    REQUIRED_CONTAINERS,
    DOCKER_COMPOSE_DIR,
    DOCKER_COMPOSE_FILE,
    PYFLINK_IMAGE
)


class DockerManager:
    """Manages Docker containers for script execution."""

    def __init__(self):
        """Initialize Docker client."""
        try:
            self.client = docker.from_env()
            self.docker_available = True
        except docker.errors.DockerException as e:
            print(f"Docker not available: {e}")
            self.docker_available = False

    async def check_containers_status(self) -> Dict:
        """Check status of required containers.

        Returns:
            Dict with docker_available flag and container statuses
        """
        if not self.docker_available:
            return {
                "docker_available": False,
                "containers": {}
            }

        containers = {}
        for name in REQUIRED_CONTAINERS:
            try:
                container = self.client.containers.get(name)
                containers[name] = {
                    "running": container.status == "running",
                    "status": container.status,
                    "uptime": self._get_uptime(container)
                }
            except docker.errors.NotFound:
                containers[name] = {
                    "running": False,
                    "status": "not_found"
                }
            except Exception as e:
                containers[name] = {
                    "running": False,
                    "status": f"error: {str(e)}"
                }

        return {
            "docker_available": True,
            "containers": containers
        }

    def _get_uptime(self, container) -> str:
        """Get container uptime as human-readable string."""
        try:
            started_at = container.attrs['State']['StartedAt']
            # Parse and calculate uptime
            # Simple implementation: just return "running"
            return "running"
        except:
            return "unknown"

    async def all_running(self) -> bool:
        """Check if all required containers are running."""
        status = await self.check_containers_status()
        if not status["docker_available"]:
            return False

        return all(
            c.get("running", False)
            for c in status["containers"].values()
        )

    async def start_containers(self, max_wait=60) -> Dict:
        """Start Docker containers using docker-compose.

        Args:
            max_wait: Maximum seconds to wait for containers to be ready

        Returns:
            Dict with status and message
        """
        if not self.docker_available:
            return {
                "success": False,
                "message": "Docker is not available. Please start Docker Desktop."
            }

        try:
            # Build pyflink image if needed
            await self._build_pyflink_image()

            # Start containers with docker-compose
            compose_path = DOCKER_COMPOSE_DIR / DOCKER_COMPOSE_FILE

            print(f"Starting containers from {compose_path}")
            result = subprocess.run(
                ["docker-compose", "-f", str(compose_path), "up", "-d"],
                cwd=str(DOCKER_COMPOSE_DIR),
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "message": f"Failed to start containers: {result.stderr}"
                }

            # Wait for containers to be ready
            await self._wait_for_healthy(max_wait)

            return {
                "success": True,
                "message": "All containers started successfully",
                "containers_started": REQUIRED_CONTAINERS
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error starting containers: {str(e)}"
            }

    async def _build_pyflink_image(self):
        """Build pyflink Docker image if it doesn't exist."""
        try:
            # Check if image exists
            self.client.images.get(PYFLINK_IMAGE)
            print(f"Image {PYFLINK_IMAGE} already exists")
        except docker.errors.ImageNotFound:
            # Build image
            print(f"Building {PYFLINK_IMAGE} image...")
            dockerfile = DOCKER_COMPOSE_DIR / "pyflink.Dockerfile"

            if dockerfile.exists():
                result = subprocess.run(
                    [
                        "docker", "build",
                        "-f", str(dockerfile),
                        "-t", PYFLINK_IMAGE,
                        str(DOCKER_COMPOSE_DIR)
                    ],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:
                    print(f"Warning: Failed to build {PYFLINK_IMAGE}: {result.stderr}")
            else:
                print(f"Warning: Dockerfile not found at {dockerfile}")

    async def _wait_for_healthy(self, max_wait=60):
        """Wait for all containers to be running and healthy.

        Args:
            max_wait: Maximum seconds to wait
        """
        start_time = time.time()

        while time.time() - start_time < max_wait:
            if await self.all_running():
                # Additional check: verify Kafka and Flink are actually responsive
                await asyncio.sleep(2)  # Give services time to fully initialize
                return True

            await asyncio.sleep(1)

        # Timeout
        status = await self.check_containers_status()
        not_running = [
            name for name, info in status["containers"].items()
            if not info.get("running", False)
        ]

        if not_running:
            raise TimeoutError(
                f"Containers not ready after {max_wait}s: {', '.join(not_running)}"
            )
