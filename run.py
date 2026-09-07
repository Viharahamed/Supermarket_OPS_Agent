import sys
from app.config import get_settings
from app.ollama_client import OllamaClient
from app.db.database import engine, Base
from app.db import models

def init_db() -> None:
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables are ready.")

def main():
    print("=== Kirana AI Agent Phase 1 Foundation Check ===")
    settings = get_settings()
    print(f"Ollama Base URL: {settings.ollama_base_url}")
    print(f"Ollama Model: {settings.ollama_model}")
    print(f"Database URL: {settings.database_url}")
    print(f"Log Level: {settings.log_level}")
    
    client = OllamaClient()
    health = client.check_health()
    print(f"\nOllama Health Status: {health.get('status')}")
    if health.get('status') == 'healthy':
        installed = [m.get('name') for m in health.get('models', [])]
        print(f"Installed Models in Ollama: {installed}")
        available = client.verify_model_availability()
        print(f"Target Model '{settings.ollama_model}' Available: {available}")
    else:
        print(f"Ollama Error/Status: {health.get('error') or health.get('code')}")

if __name__ == "__main__":
    main()
