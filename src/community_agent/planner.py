"""Step 1 — Planner: brief -> plan.json."""
from __future__ import annotations

from .brief import Brief
from .config import Config
from .llm import LLM, MODEL_WRITE
from .schemas import Plan, PlanOut


def make_plan(llm: LLM, brief: Brief, cfg: Config, model: str = MODEL_WRITE) -> Plan:
    effort = "high" if brief.mode == "campaign" else "medium"
    user = "\n".join([
        f"mode: {brief.mode}",
        f"target_platforms: {', '.join(brief.platforms)}",
        "",
        "## Brief",
        brief.to_prompt_text(),
        "",
        "Produce the plan JSON. `per_platform` must contain exactly one entry for each of: "
        f"{', '.join(brief.platforms)} (field `platform` = that name).",
    ])
    plan = llm.generate(stage="planner", system=[cfg.prompt("system"), cfg.prompt("planner")],
                        user=user, schema=PlanOut, model=model, effort=effort).to_plan()
    # Code-side guard: the plan must cover exactly the requested platforms.
    for key in ("angles", "cta_variants"):
        d = getattr(plan, key)
        for p in brief.platforms:
            d.setdefault(p, d.get("default", ""))
        for extra in [k for k in d if k not in brief.platforms]:
            d.pop(extra)
    plan.mode = brief.mode
    return plan
