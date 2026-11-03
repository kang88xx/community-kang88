"""Pydantic models for every LLM output (plan.json, <platform>/post.json, review.json).

Each model also provides the strict JSON schema sent as `output_config.format`.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- plan.json


class MediaHint(BaseModel):
    proof_point: str = Field(description="Which proof point the visual should carry")
    source: Literal["template", "asset", "clip"] = "template"
    note: str = ""


class PlanRisk(BaseModel):
    type: Literal["misleading", "spam", "platform_norm", "legal", "other"] = "other"
    text: str
    why: str = ""


class Plan(BaseModel):
    """Internal plan (dict keyed by platform). The LLM produces PlanOut; see `PlanOut.to_plan`."""
    mode: Literal["campaign", "single"]
    core_message: str
    proof_points: list[str] = Field(description="3-5 concrete facts from the brief, strongest first")
    angles: dict[str, str] = Field(description="platform -> the one angle for that platform")
    cta_variants: dict[str, str] = Field(description="platform -> CTA phrasing")
    media_hints: dict[str, MediaHint] = Field(default_factory=dict)
    risks: list[PlanRisk] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class PlatformAngle(BaseModel):
    platform: str
    angle: str = Field(description="The ONE angle for this platform")
    cta: str = Field(description="CTA phrased for this platform")
    media_hint: MediaHint


class PlanOut(BaseModel):
    """LLM-facing plan: structured outputs require additionalProperties=false on every object,
    so platform maps are lists of {platform, ...} and converted to dicts in `to_plan`."""
    mode: Literal["campaign", "single"]
    core_message: str
    proof_points: list[str] = Field(description="3-5 concrete facts from the brief, strongest first")
    per_platform: list[PlatformAngle] = Field(description="exactly one entry per requested platform")
    risks: list[PlanRisk] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    def to_plan(self) -> "Plan":
        return Plan(
            mode=self.mode, core_message=self.core_message, proof_points=self.proof_points,
            angles={e.platform: e.angle for e in self.per_platform},
            cta_variants={e.platform: e.cta for e in self.per_platform},
            media_hints={e.platform: e.media_hint for e in self.per_platform},
            risks=self.risks, open_questions=self.open_questions,
        )


# --------------------------------------------------------------------------- post.json per platform


class TelegramPost(BaseModel):
    text_html: str = Field(description="Full message, Telegram HTML, <= 4096 chars")
    caption_html: str = Field(description="Stand-alone caption for media, <= 1024 chars")
    text_plain: str = Field(description="text_html with tags stripped")
    hashtags: list[str] = Field(default_factory=list)
    alt_text: str = ""
    notes: str = ""


class Tweet(BaseModel):
    text: str
    media_refs: list[str] = Field(default_factory=list)


class XPost(BaseModel):
    tweets: list[Tweet] = Field(description="1-6 tweets; first is the hook")
    hashtags: list[str] = Field(default_factory=list)
    alt_text: str = ""
    notes: str = ""


class RedditPost(BaseModel):
    title: str
    body_markdown: str
    suggested_subreddits: list[str] = Field(default_factory=list)
    flair: str = ""
    post_type: Literal["text", "image", "video"] = "text"
    notes: str = ""


class LinkedInPost(BaseModel):
    text: str
    first_comment: str = Field(description="Links go here, posted as the first comment")
    hashtags: list[str] = Field(default_factory=list)
    alt_text: str = ""
    notes: str = ""


POST_MODELS: dict[str, type[BaseModel]] = {
    "telegram": TelegramPost,
    "x": XPost,
    "reddit": RedditPost,
    "linkedin": LinkedInPost,
}

# --------------------------------------------------------------------------- review.json


class RiskFlag(BaseModel):
    type: Literal["factual", "tone", "policy", "spam", "accessibility"]
    text: str
    why: str = ""


class PlatformReview(BaseModel):
    fit_score: Literal[1, 2, 3, 4, 5]
    clarity_score: Literal[1, 2, 3, 4, 5]
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    media_check: str = ""
    suggestions: list[str] = Field(default_factory=list)
    ready_to_post: bool


class PlatformReviewItem(PlatformReview):
    platform: str


class Review(BaseModel):
    """Internal review keyed by platform; the LLM produces ReviewOut."""
    platforms: dict[str, PlatformReview]
    cross_platform: str = ""


class ReviewOut(BaseModel):
    platforms: list[PlatformReviewItem] = Field(description="exactly one entry per platform reviewed")
    cross_platform: str = ""

    def to_review(self) -> "Review":
        return Review(
            platforms={e.platform: PlatformReview(**e.model_dump(exclude={"platform"})) for e in self.platforms},
            cross_platform=self.cross_platform,
        )


# --------------------------------------------------------------------------- strict schema helper


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema accepted by structured outputs (`output_config.format`).

    Delegates to the SDK's `anthropic.transform_schema`, which sets additionalProperties=false
    on every object, moves unsupported numeric bounds / defaults into descriptions, and keeps
    property names intact. Every model passed here must avoid `dict[str, X]` fields (use lists).
    """
    from anthropic import transform_schema

    return transform_schema(model)
