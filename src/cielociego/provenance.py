"""Provenance stamp carried by every output.

Without it, a year from now nobody can tell which version and which threshold
produced a given JSON. Records the input fingerprint too, so a retouched polygon
shows up as a mismatch instead of a mystery.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__


def _commit() -> str | None:
    """Short repository SHA, if there is one. Never raises."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, timeout=5, check=False,
        )
        sha = r.stdout.strip()
        return sha or None
    except Exception:
        return None


def fingerprint(path: str | Path) -> str | None:
    """SHA-256 of a file, to detect that the input changed."""
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]
    except Exception:
        return None


def record(**parametros: Any) -> dict[str, Any]:
    """Version, timestamp, environment and the parameters of this measurement."""
    return {
        "version": __version__,
        "commit": _commit(),
        "medido_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "sistema": platform.system(),
        "parametros": {k: v for k, v in parametros.items() if v is not None},
    }
