from app.config import get_settings

_settings = get_settings()

OLLAMA_BASE_URL = _settings.ollama_base_url
OLLAMA_MODEL = _settings.ollama_model
OLLAMA_TIMEOUT = _settings.ollama_timeout
MAX_AGENT_ITERATIONS = _settings.agent_max_iterations

