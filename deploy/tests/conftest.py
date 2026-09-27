"""Põe ``deploy/`` no ``sys.path``: os testes importam ``smoke`` como no ``make smoke``."""

import sys
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1]
if str(DEPLOY) not in sys.path:
    sys.path.insert(0, str(DEPLOY))
