"""Configuration settings for the backend."""
from pathlib import Path

# Server configuration
BACKEND_PORT = 3001
BACKEND_HOST = "0.0.0.0"

# Directory paths
BASE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
DOCKER_COMPOSE_DIR = BASE_DIR / "running" / "Docker"
DOCKER_COMPOSE_FILE = "env-compose.yml"

# Docker configuration
PYFLINK_IMAGE = "pyflink"
REQUIRED_CONTAINERS = ["jobmanager", "taskmanager", "kafka", "zookeeper"]

# Execution configuration
MAX_EXECUTIONS_HISTORY = 50  # Auto-cleanup threshold
EXECUTION_TIMEOUT = 600  # 10 minutes in seconds

# Ensure scripts directory exists
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
