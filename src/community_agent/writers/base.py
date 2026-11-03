"""Step 2 — Writer loop: generate -> validate -> retry (<= max_retries) with error feedback."""
from __future__ import annotations

import json
import typing
from dataclasses import dataclass, field

import yaml
from pydantic import BaseModel

from ..brief import Brief
from ..config import Config
from ..llm import LLM, MODEL_WRITE
from ..schemas import POST_MODELS, Plan
from ..validate import Violation, errors_only, validate_post


def empty_post(schema: type[BaseModel]) -> BaseModel:
    """A schema-valid but empty post, used when every attempt raised (so the run still packages)."""
    values = {}
    for name, info in schema.model_fields.items():
        if not info.is_required():
            continue
        ann = info.annotation
        origin = typing.get_origin(ann)
        if origin is list:
            values[name] = []
        elif origin is typing.Literal:
            values[name] = typing.get_args(ann)[0]
        elif ann is bool:
            values[name] = False
        elif ann in (int, float):
            values[name] = 0
        else:
            values[name] = ""
    return schema.model_validate(values)


@dataclass
class WriterResult:
    platform: str
    post: BaseModel
    violations: list[Violation] = field(default_factory=list)
    attempts: int = 1
    history: list[dict] = field(default_factory=list)  # [{attempt, errors}] for REVIEW.md

    @property
    def ok(self) -> bool:
        return not errors_only(self.violations)


def _constraints_block(platform: str, brief: Brief, cfg: Config) -> str:
    rules = cfg.platform(platform)
    langs = brief.languages_for(platform, rules.get("language"))
    text_rules = {"language": langs, **rules.get("text", {})}
    return "# Hard constraints for this platform (enforced by code)\n" + yaml.safe_dump(
        {platform: text_rules}, allow_unicode=True, sort_keys=False)


def _user_turn(platform: str, brief: Brief, plan: Plan, prev: BaseModel | None,
               errors: list[Violation]) -> str:
    parts = [
        f"target_platform: {platform}",
        f"mode: {brief.mode}",
        "",
        "## Brief",
        brief.to_prompt_text(),
        "",
        "## Plan",
        f"core_message: {plan.core_message}",
        "proof_points:\n" + "\n".join(f"- {p}" for p in plan.proof_points),
        f"angle: {plan.angles.get(platform, '')}",
        f"cta: {plan.cta_variants.get(platform, brief.cta)}",
    ]
    if plan.risks:
        parts.append("risks to avoid:\n" + "\n".join(f"- {r.text}" for r in plan.risks))
    if brief.platform_notes.get(platform):
        parts.append(f"platform note from the author: {brief.platform_notes[platform]}")
    if prev is not None and errors:
        parts += [
            "",
            "## previous_draft",
            json.dumps(prev.model_dump(), ensure_ascii=False, indent=2),
            "",
            "## validation_errors",
            json.dumps([e.to_dict() for e in errors], ensure_ascii=False, indent=2),
            "",
            "Fix ONLY what the validation_errors require. Keep everything else identical to previous_draft.",
        ]
    else:
        parts += ["", f"Write the {platform} post now. Return only the JSON."]
    return "\n".join(parts)


def write_post(llm: LLM, platform: str, brief: Brief, plan: Plan, cfg: Config,
               model: str = MODEL_WRITE, max_retries: int = 2) -> WriterResult:
    schema = POST_MODELS[platform]
    system = [cfg.prompt("system"), cfg.prompt(platform), _constraints_block(platform, brief, cfg)]
    prev: BaseModel | None = None
    errors: list[Violation] = []
    history: list[dict] = []
    post: BaseModel | None = None
    violations: list[Violation] = []

    for attempt in range(1, max_retries + 2):
        try:
            post = llm.generate(stage=f"writer:{platform}#{attempt}", system=system,
                                user=_user_turn(platform, brief, plan, prev, errors), schema=schema, model=model)
        except Exception as exc:  # RefusedError, max_tokens RuntimeError, JSON/pydantic errors, API errors
            # Count the failure as a violation so the run still packages and REVIEW.md shows it.
            err = Violation("llm_error", "-", type(exc).__name__, "-", f"LLM call failed: {exc}")
            history.append({"attempt": attempt, "errors": [err.to_dict()]})
            violations = [err]
            errors = []  # nothing to feed back; next attempt is a plain retry of the same prompt
            continue
        violations = validate_post(platform, post, brief, cfg)
        errors = errors_only(violations)
        history.append({"attempt": attempt, "errors": [e.to_dict() for e in errors]})
        if not errors:
            return WriterResult(platform, post, violations, attempt, history)
        prev = post

    if post is None:
        post = empty_post(schema)
    return WriterResult(platform, post, violations, max_retries + 1, history)
