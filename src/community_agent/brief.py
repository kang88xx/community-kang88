"""Brief parsing: briefs/*.md (YAML frontmatter + markdown body) -> Brief model."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

import frontmatter
from pydantic import BaseModel, Field, field_validator, model_validator

from .config import PLATFORMS

Goal = Literal["announce", "educate", "engage", "recruit", "promote"]


class Link(BaseModel):
    label: str = ""
    url: str


class Asset(BaseModel):
    path: str
    caption: str = ""


class RedditOptions(BaseModel):
    subreddits: list[str] = Field(default_factory=list)
    post_type: Literal["text", "image", "video"] = "text"


class Brief(BaseModel):
    title: str
    slug: str
    goal: Goal = "announce"
    audience: str = ""
    tone: str = ""
    language: dict[str, list[str]] = Field(default_factory=dict)  # only what the author wrote
    cta: str = ""
    links: list[Link] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    media: dict[str, list[str]] = Field(default_factory=lambda: {"default": ["jpg"]})
    platforms: list[str] = Field(default_factory=lambda: list(PLATFORMS))
    reddit: RedditOptions = Field(default_factory=RedditOptions)
    body: str = ""
    avoid: list[str] = Field(default_factory=list)
    platform_notes: dict[str, str] = Field(default_factory=dict)
    source_path: str = ""

    # --- normalisation -------------------------------------------------
    @field_validator("language", mode="before")
    @classmethod
    def _language(cls, v: Any) -> dict[str, list[str]]:
        if v is None:
            return {}
        if isinstance(v, str):
            return {"default": [v]}
        if isinstance(v, list):
            return {"default": [str(x) for x in v]}
        out: dict[str, list[str]] = {}
        for k, val in dict(v).items():
            out[k] = [val] if isinstance(val, str) else [str(x) for x in val]
        return out

    @field_validator("media", mode="before")
    @classmethod
    def _media(cls, v: Any) -> dict[str, list[str]]:
        if v is None:
            return {"default": ["jpg"]}
        if isinstance(v, list):
            return {"default": [str(x) for x in v]}
        out: dict[str, list[str]] = {}
        for k, val in dict(v).items():
            out[k] = [val] if isinstance(val, str) else [str(x) for x in val]
        out.setdefault("default", ["jpg"])
        return out

    @field_validator("links", mode="before")
    @classmethod
    def _links(cls, v: Any) -> list[dict[str, str]]:
        out = []
        for item in v or []:
            if isinstance(item, str):
                out.append({"label": "", "url": item})
            else:
                out.append(item)
        return out

    @field_validator("assets", mode="before")
    @classmethod
    def _assets(cls, v: Any) -> list[dict[str, str]]:
        return [{"path": a} if isinstance(a, str) else a for a in (v or [])]

    @field_validator("platforms", mode="before")
    @classmethod
    def _platforms(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = [p.strip() for p in v.split(",")]
        v = [str(p).lower() for p in (v or PLATFORMS)]
        unknown = [p for p in v if p not in PLATFORMS]
        if unknown:
            raise ValueError(f"Unknown platform(s): {unknown}. Known: {list(PLATFORMS)}")
        return v

    @model_validator(mode="after")
    def _slug_default(self) -> "Brief":
        # Always slugified: a frontmatter slug like "../x" must not escape output/.
        self.slug = slugify(self.slug or self.title)
        return self

    # --- helpers --------------------------------------------------------
    @property
    def mode(self) -> Literal["campaign", "single"]:
        return "single" if len(self.platforms) == 1 else "campaign"

    def languages_for(self, platform: str, fallback: list[str] | None = None) -> list[str]:
        """Precedence: brief per-platform > brief default (explicit) > platforms.yaml > ko."""
        return (self.language.get(platform) or self.language.get("default")
                or (list(fallback) if fallback else None) or ["ko"])

    def media_for(self, platform: str) -> list[str]:
        return self.media.get(platform) or self.media.get("default") or []

    def to_prompt_text(self) -> str:
        """Human-readable rendering used inside LLM user turns."""
        lines = [
            f"# {self.title}",
            f"goal: {self.goal}",
            f"audience: {self.audience}",
            f"tone: {self.tone}",
            f"languages: {self.language or '(platform defaults)'}",
            f"cta: {self.cta}",
            f"platforms: {', '.join(self.platforms)}",
        ]
        if self.links:
            lines.append("links:")
            lines += [f"  - {l.label or '(no label)'}: {l.url}" for l in self.links]
        if self.assets:
            lines.append("assets:")
            lines += [f"  - {a.path}: {a.caption}" for a in self.assets]
        if self.reddit.subreddits:
            lines.append(f"reddit.subreddits: {', '.join(self.reddit.subreddits)}")
        if self.avoid:
            lines.append("avoid (never use these expressions): " + " | ".join(self.avoid))
        if self.platform_notes:
            lines.append("platform notes:")
            lines += [f"  - {k}: {v}" for k, v in self.platform_notes.items()]
        lines += ["", "## Body", self.body.strip()]
        return "\n".join(lines)


_SLUG_RE = re.compile(r"[^a-z0-9가-힣]+")


def slugify(text: str, max_len: int = 40) -> str:
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "post"


_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)


def _sections(body: str) -> dict[str, str]:
    """Split markdown body on `## heading` lines -> {heading: text}."""
    out: dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(body))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out[m.group(1).strip()] = body[m.end():end].strip()
    return out


def _bullets(text: str) -> list[str]:
    items = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("-", "*", "•")):
            items.append(line.lstrip("-*• ").strip().strip('"“”'))
    return items


def _avoid_from(sections: dict[str, str]) -> list[str]:
    out: list[str] = []
    for heading, text in sections.items():
        h = heading.lower()
        if "피해야" in h or "avoid" in h or "금지" in h:
            for item in _bullets(text):
                # '"혁명적", "업계 최초"' -> ['혁명적', '업계 최초']
                parts = [p.strip().strip('"“”\'') for p in re.split(r'",\s*"|,\s*', item)]
                out += [p for p in parts if p]
    return out


def _notes_from(sections: dict[str, str]) -> dict[str, str]:
    notes: dict[str, str] = {}
    for heading, text in sections.items():
        h = heading.lower()
        if "플랫폼별" in h or "platform" in h:
            for item in _bullets(text):
                if ":" in item:
                    k, v = item.split(":", 1)
                    k = k.strip().lower()
                    if k in PLATFORMS:
                        notes[k] = v.strip()
    return notes


def load_brief(path: str | Path) -> Brief:
    path = Path(path)
    post = frontmatter.load(str(path), encoding="utf-8")
    meta: dict[str, Any] = dict(post.metadata)
    body: str = post.content
    sections = _sections(body)
    meta.setdefault("avoid", [])
    meta["avoid"] = list(meta["avoid"]) + _avoid_from(sections)
    meta.setdefault("platform_notes", {})
    meta["platform_notes"] = {**_notes_from(sections), **dict(meta["platform_notes"])}
    meta["body"] = body
    meta["source_path"] = str(path)
    if not meta.get("slug"):
        meta["slug"] = slugify(path.stem)
    return Brief.model_validate(meta)
