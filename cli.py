# cli.py
"""Interactive CLI runner for Kirana AI Agent.

Allows live testing of user queries against local Ollama (gemma2:2b) and
Phase 9 Tool Registry / SQLite database.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent))

from app.db.database import init_db
from app.agent import handle_message
from app.agent.config import OLLAMA_BASE_URL, OLLAMA_MODEL


def main():
    print("=" * 60)
    print("  🏪 KIRANA AI AGENT — LIVE INTERACTIVE TESTING CLI")
    print("=" * 60)
    print(f"Ollama URL : {OLLAMA_BASE_URL}")
    print(f"Target Model: {OLLAMA_MODEL}")
    print("-" * 60)

    # Initialize DB tables
    init_db()
    print("Database tables initialized. Ready for queries.")
    print("Type your query below (or 'exit' / 'quit' to stop):\n")

    while True:
        try:
            user_input = input("\nUser > ").strip()
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit", "q"}:
                print("Exiting Kirana AI Agent CLI. Goodbye!")
                break

            print("\n🤖 Agent thinking & executing tools...\n")
            response = handle_message(user_input)

            print("=" * 60)
            print("AGENT RESPONSE:")
            print("=" * 60)
            print(response.content)
            print("=" * 60)
            if response.metadata:
                print(f"Metadata: {response.metadata}")

        except KeyboardInterrupt:
            print("\nExiting Kirana AI Agent CLI. Goodbye!")
            break
        except Exception as exc:
            print(f"\n❌ Exception occurred: {exc}")


if __name__ == "__main__":
    main()
