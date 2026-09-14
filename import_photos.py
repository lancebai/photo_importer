#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Auto-detect and switch to local virtualenv if not already running in it
project_root = Path(__file__).resolve().parent
venv_python = project_root / "venv" / "bin" / "python"

if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
    os.execv(str(venv_python), [str(venv_python)] + sys.argv)

# Ensure src is in sys.path
sys.path.insert(0, str(project_root))

from src.cli import main

if __name__ == "__main__":
    main()
