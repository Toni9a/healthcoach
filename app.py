from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SITE_DIR = ROOT / "site"
if str(SITE_DIR) not in sys.path:
    sys.path.insert(0, str(SITE_DIR))

from health_bridge_server import app, bootstrap  # noqa: E402


bootstrap()
