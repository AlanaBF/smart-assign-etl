"""
Wrapper for the fake report generator script.
"""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "make_fake_flowcase_reports.py"
    subprocess.run([sys.executable, str(script)], check=True, cwd=repo_root)


__all__ = ["main"]
