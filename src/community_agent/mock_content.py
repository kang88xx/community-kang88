"""Canned, schema-valid content for MockLLM (dry-run / tests). No network."""
from __future__ import annotations

import re
from typing import Any

_TITLE_RE = re.compile(r"^# (.+)$", re.M)
_CTA_RE = re.compile(r"^cta: (.*)$", re.M)
_URL_RE = re.compile(r"https?://\S+")
_PLATFORMS_RE = re.compile(r"^platforms: (.*)$", re.M)
_TARGET_RE = re.compile(r"^target_platform: (\w+)$", re.M)


def _ctx(user: str) -> dict[str, Any]:
    title = (_TITLE_RE.search(user) or [None, "Untitled"])[1].strip()
    cta = (_CTA_RE.search(user) or [None, "Learn more"])[1].strip()
    urls = _URL_RE.findall(user)
    plats_m = _PLATFORMS_RE.search(user)
    platforms = [p.strip() for p in plats_m.group(1).split(",")] if plats_m else ["telegram", "x", "reddit", "linkedin"]
    return {"title": title, "cta": cta, "url": urls[0] if urls else "https://example.com", "platforms": platforms}


def build(schema_name: str, user: str) -> dict[str, Any]:
    c = _ctx(user)
    t = c["title"]
    url = c["url"]
    if schema_name == "PlanOut":
        plats = c["platforms"]
        return {
            "mode": "single" if len(plats) == 1 else "campaign",
            "core_message": f"{t}: what changed and why it matters.",
            "proof_points": ["Proof point 1 from the brief", "Proof point 2 from the brief", "Proof point 3 from the brief"],
            "per_platform": [{"platform": p, "angle": f"{p} angle for {t}", "cta": c["cta"],
                              "media_hint": {"proof_point": "Proof point 1 from the brief", "source": "template", "note": "stat card"}}
                             for p in plats],
            "risks": [{"type": "misleading", "text": "Numbers are placeholders in dry-run", "why": "mock backend"}],
            "open_questions": ["(dry-run) Confirm the numbers before publishing"],
        }
    if schema_name == "TelegramPost":
        html = (f"<b>{t}</b>\n\n• Proof point 1 from the brief\n• Proof point 2 from the brief\n"
                f"• Proof point 3 from the brief\n\n<a href=\"{url}\">자세히 보기</a>\n\n{c['cta']}")
        plain = re.sub(r"<[^>]+>", "", html)
        return {"text_html": html, "caption_html": html[:1000], "text_plain": plain,
                "hashtags": [], "alt_text": f"Card: {t}", "notes": "dry-run"}
    if schema_name == "XPost":
        return {
            "tweets": [
                {"text": f"{t[:120]} — here's what changed.", "media_refs": ["card_1600x900.jpg"]},
                {"text": "Proof point 1 from the brief. Proof point 2 from the brief.", "media_refs": []},
                {"text": f"{c['cta'][:150]} {url}", "media_refs": []},
            ],
            "hashtags": [], "alt_text": f"Card: {t}", "notes": "dry-run",
        }
    if schema_name == "RedditPost":
        body = ("**Context**\n\nWhy we did this (2-3 sentences).\n\n**What we did**\n\n"
                "Proof point 1 from the brief. Proof point 2 from the brief.\n\n**What went wrong**\n\n"
                "Honest note about trade-offs.\n\n**Question**\n\nHow do you handle this?\n\n"
                f"Links (I work on this): [{t}]({url})")
        return {"title": f"{t} — what we learned", "body_markdown": body,
                "suggested_subreddits": ["r/SideProject"], "flair": "Discussion", "post_type": "text", "notes": "dry-run"}
    if schema_name == "LinkedInPost":
        text = (f"{t}: the short version of what changed and why it matters for teams.\n\n"
                "Proof point 1 from the brief.\n\nProof point 2 from the brief.\n\nProof point 3 from the brief.\n\n"
                f"{c['cta']}\n\n#ProductUpdate #Engineering #Teamwork")
        return {"text": text, "first_comment": f"Details: {url}", "hashtags": ["ProductUpdate", "Engineering", "Teamwork"],
                "alt_text": f"Card: {t}", "notes": "dry-run"}
    if schema_name == "ReviewOut":
        plats = c["platforms"]
        return {
            "platforms": [{"platform": p, "fit_score": 4, "clarity_score": 4, "risk_flags": [], "media_check": "n/a (text only)",
                           "suggestions": ["(dry-run) tighten the hook"], "ready_to_post": True} for p in plats],
            "cross_platform": "(dry-run) consistent",
        }
    raise ValueError(f"MockLLM has no canned content for schema {schema_name}")
