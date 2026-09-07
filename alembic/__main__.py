# alembic/__main__.py
"""Main entry point for executing Alembic CLI commands via `python -m alembic`.

Bridges execution from repository `alembic/` directory to installed library `alembic` package.
"""

from __future__ import annotations

import os
import sys

# Save original sys.path
_original_sys_path = list(sys.path)

# Unshadow site-packages alembic by temporarily removing current working directory from sys.path
_cwd = os.path.abspath(os.getcwd())
sys.path = [p for p in sys.path if p and os.path.abspath(p) != _cwd]

# Remove local alembic namespace package if cached in sys.modules without __file__
if "alembic" in sys.modules:
    _mod = sys.modules["alembic"]
    if not getattr(_mod, "__file__", None):
        del sys.modules["alembic"]

try:
    from alembic.config import main
finally:
    # Restore original sys.path so env.py and application imports work cleanly
    sys.path = _original_sys_path

if __name__ == "__main__":
    sys.exit(main())
