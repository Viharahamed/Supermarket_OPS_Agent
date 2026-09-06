import requests
from typing import Dict, Any, List
from app.config import get_settings

class OllamaClient:
    """Client for interacting with local Ollama service and verifying model connectivity."""

    def __init__(self, base_url: str = None, model: str = None):
        settings = get_settings()
        self.base_url = (base_url or settings.ollama_base_url).rstrip('/')
        self.model = model or settings.ollama_model

    def check_health(self) -> Dict[str, Any]:
        """Check if Ollama service is reachable."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "code": 200,
                    "models": response.json().get("models", [])
                }
            return {
                "status": "unhealthy",
                "code": response.status_code,
                "error": response.text
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    def verify_model_availability(self) -> bool:
        """Verify if the configured model (e.g. qwen3:8b) is installed in Ollama."""
        health = self.check_health()
        if health.get("status") != "healthy":
            return False
        
        models = health.get("models", [])
        model_names = [m.get("name") for m in models]
        
        # Check exact or prefix match (e.g. qwen3:8b or qwen3:latest)
        return any(
            self.model in name or name.startswith(self.model.split(':')[0])
            for name in model_names
        )

    def generate_response(self, prompt: str, system_prompt: str = None) -> Dict[str, Any]:
        """Send a test generation prompt to the local Ollama model."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            if response.status_code == 200:
                return {
                    "success": True,
                    "response": response.json().get("response", ""),
                    "raw": response.json()
                }
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {response.text}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
