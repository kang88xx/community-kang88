"""Anthropic client wrapper: structured output, prompt caching, server-side fallbacks, usage log.

Two backends:
  * AnthropicLLM — real calls (client.beta.messages.create + output_config.format)
  * MockLLM      — deterministic canned JSON per schema for --dry-run / tests (no network, no key)
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from .schemas import strict_schema

T = TypeVar("T", bound=BaseModel)

MODEL_WRITE = "claude-opus-5-5"
MODEL_REVIEW = "claude-haiku-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class UsageRecord:
    stage: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    seconds: float = 0.0
    stop_reason: str = ""
    request_id: str = ""
    served_by: str = ""


@dataclass
class UsageLog:
    records: list[UsageRecord] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, rec: UsageRecord) -> None:
        with self._lock:  # writers run in a thread pool
            self.records.append(rec)

    def totals(self) -> dict[str, int]:
        keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
        return {k: sum(getattr(r, k) for r in self.records) for k in keys}

    def dump(self, path: Path) -> None:
        path.write_text(
            json.dumps({"calls": [asdict(r) for r in self.records], "totals": self.totals()},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class LLM(Protocol):
    usage: UsageLog

    def generate(self, *, stage: str, system: list[str], user: str, schema: type[T],
                 model: str = MODEL_WRITE, effort: str = "high") -> T: ...


class RefusedError(RuntimeError):
    pass


# --------------------------------------------------------------------------- real backend


class AnthropicLLM:
    def __init__(self, client: Any | None = None, max_tokens: int = 16000) -> None:
        import anthropic  # local import so --dry-run works without the package configured

        self.client = client or anthropic.Anthropic()
        self.max_tokens = max_tokens
        self.usage = UsageLog()

    def generate(self, *, stage: str, system: list[str], user: str, schema: type[T],
                 model: str = MODEL_WRITE, effort: str = "high") -> T:
        # `system` = [shared_prompt, platform_prompt, constraints]. Two breakpoints: the shared
        # first block (prefix the N writers have in common) and the last block (retries of the
        # same platform). Caching only kicks in once a prefix exceeds the model's minimum
        # cacheable length, so expect cache_read=0 while prompts are short.
        system_blocks: list[dict[str, Any]] = [{"type": "text", "text": s} for s in system if s]
        if system_blocks:
            system_blocks[0]["cache_control"] = {"type": "ephemeral"}
            system_blocks[-1]["cache_control"] = {"type": "ephemeral"}

        t0 = time.monotonic()
        response = self.client.beta.messages.create(
            model=model,
            max_tokens=self.max_tokens,
            system=system_blocks,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": strict_schema(schema)}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        elapsed = time.monotonic() - t0

        usage = getattr(response, "usage", None)
        self.usage.add(UsageRecord(
            stage=stage, model=model,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            seconds=round(elapsed, 2),
            stop_reason=str(getattr(response, "stop_reason", "")),
            request_id=str(getattr(response, "_request_id", "") or ""),
            served_by=str(getattr(response, "model", model)),
        ))

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            raise RefusedError(f"{stage}: request refused ({getattr(details, 'category', '?')}): "
                               f"{getattr(details, 'explanation', '')}"
                               f" recommended_model={getattr(details, 'recommended_model', None)}")
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"{stage}: output truncated at max_tokens={self.max_tokens}; raise it")

        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), None)
        if text is None:
            raise RuntimeError(f"{stage}: no text block in response (stop_reason={response.stop_reason})")
        return schema.model_validate(json.loads(text))


# --------------------------------------------------------------------------- mock backend


class MockLLM:
    """Fills every schema with plausible placeholder content derived from the user turn.

    Used by `community run --dry-run` and the test-suite. Deterministic.
    """

    def __init__(self, fail_stages: dict[str, Exception] | None = None) -> None:
        self.usage = UsageLog()
        self.calls: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.fail_stages = fail_stages or {}  # {"writer:x#1": RefusedError(...)} for tests

    def generate(self, *, stage: str, system: list[str], user: str, schema: type[T],
                 model: str = MODEL_WRITE, effort: str = "high") -> T:
        with self._lock:
            self.calls.append({"stage": stage, "model": model, "user": user, "schema": schema.__name__})
        if stage in self.fail_stages:
            raise self.fail_stages[stage]
        self.usage.add(UsageRecord(stage=stage, model=model + " (mock)", input_tokens=len(user) // 4,
                                   output_tokens=200, stop_reason="end_turn"))
        from . import mock_content

        data = mock_content.build(schema.__name__, user)
        return schema.model_validate(data)
