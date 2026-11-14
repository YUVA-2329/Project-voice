import os
import sys
from pathlib import Path

# Ensure UTF-8 everywhere
os.environ["PYTHONUTF8"] = "1"
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
sys.stdout.reconfigure(encoding="utf-8")

import pytest

def main():
    test_file = str(backend_dir / "tests" / "test_multilingual.py")
    print(f"Running pytest on {test_file}...")
    code = pytest.main([test_file, "-v", "-o", "addopts="])
    print(f"Pytest exited with code {code}")
    sys.exit(code)

if __name__ == "__main__":
    main()
