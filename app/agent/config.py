import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def get_env(var_name: str, default: str | None = None) -> str:
    return os.getenv(var_name, default)


# Ollama configuration
OLLAMA_BASE_URL = get_env("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = get_env("OLLAMA_MODEL", "gemma2:2b")
OLLAMA_TIMEOUT = int(get_env("OLLAMA_TIMEOUT", "60"))

# Agent loop configuration
MAX_AGENT_ITERATIONS = int(get_env("MAX_AGENT_ITERATIONS", "8"))
