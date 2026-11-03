"""Step 6 — Reviewer (cheap model): scores + risk flags, never rewrites."""
from __future__ import annotations

import json

from .brief import Brief
from .config import Config
from .llm import LLM, MODEL_REVIEW
from .schemas import Plan, Review, ReviewOut
from .writers.base import WriterResult


def review_posts(llm: LLM, brief: Brief, plan: Plan, results: dict[str, WriterResult], cfg: Config,
                 model: str = MODEL_REVIEW) -> Review:
    posts = {p: r.post.model_dump() for p, r in results.items()}
    user = "\n".join([
        f"platforms: {', '.join(results)}",
        f"mode: {brief.mode}",
        "",
        "## Brief",
        brief.to_prompt_text(),
        "",
        "## Plan",
        json.dumps(plan.model_dump(), ensure_ascii=False, indent=2),
        "",
        "## Posts",
        json.dumps(posts, ensure_ascii=False, indent=2),
        "",
        "No media was rendered in this run (text-only phase); set media_check to 'n/a (text only)'.",
        f"`platforms` must contain exactly one entry per platform: {', '.join(results)}."
        + ("" if len(results) > 1 else " Set cross_platform to 'n/a (single platform)'."),
    ])
    review = llm.generate(stage="reviewer", system=[cfg.prompt("system"), cfg.prompt("reviewer")],
                          user=user, schema=ReviewOut, model=model, effort="low").to_review()
    # Reviewer's ready_to_post can only be true when the validator also passed.
    for p, r in results.items():
        if p in review.platforms and not r.ok:
            review.platforms[p].ready_to_post = False
    return review
