"""Lets the scenario tests import ``fakes`` (importlib mode puts no test directory on the path)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
