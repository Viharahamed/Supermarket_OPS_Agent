# run_bot.py
"""Top-level runner script for Kirana AI Agent Telegram Bot."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent))

from app.telegram.bot import main

if __name__ == "__main__":
    main()
