"""Project-root discovery. Everything else (config, prompts, output) hangs off ROOT."""
from __future__ import annotations

import os
from pathlib import Path


def find_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or CWD) until a folder containing config/platforms.yaml is found.

    COMMUNITY_ROOT env var overrides the search.
    """
    env = os.environ.get("COMMUNITY_ROOT")
    if env:
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "config" / "platforms.yaml").exists():
            return candidate
    raise FileNotFoundError(
        "Could not find project root (a folder containing config/platforms.yaml). "
        "Run from inside the project or set COMMUNITY_ROOT."
    )


ROOT = find_root()
CONFIG_DIR = ROOT / "config"
PROMPTS_DIR = ROOT / "prompts"
OUTPUT_DIR = ROOT / "output"
