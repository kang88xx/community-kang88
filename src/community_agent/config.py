"""Load platforms.yaml / brand.yaml / prompts once per run."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .paths import CONFIG_DIR, PROMPTS_DIR

PLATFORMS = ("telegram", "x", "reddit", "linkedin")


@dataclass
class Config:
    platforms: dict[str, Any]
    brand: dict[str, Any]
    prompts: dict[str, str] = field(default_factory=dict)

    def platform(self, name: str) -> dict[str, Any]:
        if name not in self.platforms:
            raise KeyError(f"Unknown platform '{name}' (known: {', '.join(self.platforms)})")
        return self.platforms[name]

    def prompt(self, name: str) -> str:
        if name not in self.prompts:
            raise KeyError(f"Missing prompt '{name}' in {PROMPTS_DIR}")
        return self.prompts[name]


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache(maxsize=1)
def load_config() -> Config:
    prompts = {p.stem: p.read_text(encoding="utf-8") for p in sorted(PROMPTS_DIR.glob("*.md"))}
    return Config(
        platforms=_read_yaml(CONFIG_DIR / "platforms.yaml"),
        brand=_read_yaml(CONFIG_DIR / "brand.yaml"),
        prompts=prompts,
    )
