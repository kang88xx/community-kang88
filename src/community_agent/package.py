"""Step 7 — Packager: output/<run_id>/ with copy-paste files and REVIEW.md."""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .brief import Brief
from .llm import UsageLog
from .schemas import Plan, Review
from .validate import hashtags_in, strip_html, x_weighted_length
from .writers.base import WriterResult


@dataclass
class RunPackage:
    run_id: str
    out_dir: Path
    ready: bool


def run_id_for(brief: Brief, today: date | None = None) -> str:
    d = (today or date.today()).isoformat()
    suffix = f"_{brief.platforms[0]}" if brief.mode == "single" else ""
    return f"{d}_{brief.slug}{suffix}"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _json(path: Path, data) -> None:
    _write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


# --------------------------------------------------------------------------- per-platform copy files


def _platform_files(platform: str, post, out: Path) -> dict[str, str]:
    """Write post.json + copy-paste files. Returns {label: relative path} for REVIEW.md."""
    files: dict[str, str] = {}
    _json(out / "post.json", post.model_dump())
    files["post.json"] = f"{platform}/post.json"
    if platform == "telegram":
        _write(out / "post.html", post.text_html + "\n")
        _write(out / "caption.html", post.caption_html + "\n")
        files["post.html"] = f"{platform}/post.html"
        files["caption.html"] = f"{platform}/caption.html"
    elif platform == "x":
        _write(out / "thread.txt", "\n\n---\n\n".join(t.text for t in post.tweets) + "\n")
        files["thread.txt"] = f"{platform}/thread.txt"
    elif platform == "reddit":
        _write(out / "post.md", f"# {post.title}\n\n{post.body_markdown}\n")
        files["post.md"] = f"{platform}/post.md"
    elif platform == "linkedin":
        _write(out / "post.txt", post.text + "\n")
        _write(out / "first_comment.txt", post.first_comment + "\n")
        files["post.txt"] = f"{platform}/post.txt"
        files["first_comment.txt"] = f"{platform}/first_comment.txt"
    return files


# --------------------------------------------------------------------------- REVIEW.md


def _limits_line(platform: str, post, rules: dict) -> str:
    t = rules["text"]
    if platform == "telegram":
        plain = strip_html(post.text_html)
        return (f"text {len(plain)}/{t['max_chars']} · caption {len(strip_html(post.caption_html))}/{t['caption_max_chars']} · "
                f"hashtags {len(hashtags_in(plain))}/{t['hashtags']['max']}")
    if platform == "x":
        lens = ", ".join(str(x_weighted_length(tw.text)) for tw in post.tweets)
        tags = sum(len(hashtags_in(tw.text)) for tw in post.tweets)
        return f"{len(post.tweets)} tweets · weighted chars [{lens}]/{t['max_chars']} · hashtags {tags}/{t['hashtags']['max']}"
    if platform == "reddit":
        return f"title {len(post.title)}/{t['title_max_chars']} · body {len(post.body_markdown)}/{t['body_max_chars']} · hashtags 0"
    if platform == "linkedin":
        hook = post.text.strip().split("\n\n", 1)[0]
        return (f"text {len(post.text)}/{t['max_chars']} · hook {len(hook)}/{t['hook_max_chars']} · "
                f"hashtags {len(hashtags_in(post.text))} ({t['hashtags']['min']}-{t['hashtags']['max']}) · first_comment {len(post.first_comment)}/{t['first_comment_max_chars']}")
    return ""


def _preview_text(platform: str, post) -> str:
    if platform == "telegram":
        return post.text_plain
    if platform == "x":
        return "\n\n---\n\n".join(f"{i + 1}. {tw.text}" for i, tw in enumerate(post.tweets))
    if platform == "reddit":
        return f"**{post.title}**\n\n{post.body_markdown}"
    if platform == "linkedin":
        return post.text + ("\n\n[first comment] " + post.first_comment if post.first_comment else "")
    return ""


def _quote(text: str) -> str:
    return "\n".join("> " + line if line.strip() else ">" for line in text.strip().splitlines())


def _status(result: WriterResult, pr) -> str:
    if not result.ok:
        return "❌ validator errors"
    if pr is not None and not pr.ready_to_post:
        return "⚠️ reviewer flagged"
    return "✅ ready"


def build_review_md(brief: Brief, plan: Plan, results: dict[str, WriterResult], review: Review | None,
                    cfg, run_id: str, files: dict[str, dict[str, str]]) -> str:
    L: list[str] = []
    L += [f"# REVIEW — {brief.title}", "",
          f"- run: `{run_id}` · mode: **{brief.mode}** · platforms: {', '.join(results)}",
          f"- brief: `{Path(brief.source_path).name}` · goal: {brief.goal} · cta: {brief.cta}", ""]

    L += ["## Summary", "", "| platform | status | attempts | fit | clarity | limits |", "|---|---|---|---|---|---|"]
    for p, r in results.items():
        pr = review.platforms.get(p) if review else None
        fit = pr.fit_score if pr else "-"
        cla = pr.clarity_score if pr else "-"
        L.append(f"| {p} | {_status(r, pr)} | {r.attempts} | {fit} | {cla} | {_limits_line(p, r.post, cfg.platform(p))} |")
    L.append("")

    L += ["## Plan", "", f"**Core message:** {plan.core_message}", "", "**Proof points:**"]
    L += [f"- {pp}" for pp in plan.proof_points]
    if plan.risks:
        L += ["", "**Risks:**"] + [f"- [{r.type}] {r.text}" + (f" — {r.why}" if r.why else "") for r in plan.risks]
    if plan.open_questions:
        L += ["", "**Open questions (fill in before publishing):**"] + [f"- {q}" for q in plan.open_questions]
    if review and review.cross_platform:
        L += ["", f"**Cross-platform:** {review.cross_platform}"]
    L.append("")

    for p, r in results.items():
        pr = review.platforms.get(p) if review else None
        L += [f"## {p}", "", f"**Angle:** {plan.angles.get(p, '')}", "",
              "**Files:** " + " · ".join(f"[{k}]({v})" for k, v in files[p].items()), "",
              "**Text:**", "", _quote(_preview_text(p, r.post)), ""]
        extras = []
        if p == "x" and r.post.hashtags:
            extras.append(f"hashtags: {' '.join('#' + h for h in r.post.hashtags)}")
        if p == "reddit":
            extras.append(f"subreddits: {', '.join(r.post.suggested_subreddits) or '-'} · flair: {r.post.flair or '-'} · type: {r.post.post_type}")
        if getattr(r.post, "alt_text", ""):
            extras.append(f"alt_text: {r.post.alt_text}")
        if getattr(r.post, "notes", ""):
            extras.append(f"writer notes: {r.post.notes}")
        if extras:
            L += ["- " + e for e in extras] + [""]
        if r.violations:
            L += ["**Validator:**"] + [f"- {'❌' if v.severity == 'error' else '⚠️'} `{v.rule}` {v.field}: {v.message}" for v in r.violations] + [""]
        else:
            L += ["**Validator:** all checks passed", ""]
        if pr:
            L += [f"**Reviewer:** fit {pr.fit_score}/5 · clarity {pr.clarity_score}/5 · ready_to_post: {pr.ready_to_post}"]
            L += [f"- 🚩 [{f.type}] {f.text}" + (f" — {f.why}" if f.why else "") for f in pr.risk_flags]
            L += [f"- 💡 {s}" for s in pr.suggestions]
            if pr.media_check:
                L += [f"- media: {pr.media_check}"]
            L.append("")
    return "\n".join(L).rstrip() + "\n"


# --------------------------------------------------------------------------- entry


def package_run(brief: Brief, plan: Plan, results: dict[str, WriterResult], review: Review | None,
                usage: UsageLog, cfg, output_root: Path, today: date | None = None) -> RunPackage:
    run_id = run_id_for(brief, today)
    out = output_root / run_id
    n = 2
    while out.exists():  # never overwrite an earlier run of the same brief on the same day
        out = output_root / f"{run_id}-{n}"
        n += 1
    run_id = out.name
    out.mkdir(parents=True)

    if brief.source_path and Path(brief.source_path).exists():
        shutil.copy(brief.source_path, out / "brief.md")
    _json(out / "plan.json", plan.model_dump())
    if review:
        _json(out / "review.json", review.model_dump())
    files = {p: _platform_files(p, r.post, out / p) for p, r in results.items()}
    _json(out / "validation.json", {p: {"ok": r.ok, "attempts": r.attempts, "history": r.history,
                                        "violations": [v.to_dict() for v in r.violations]} for p, r in results.items()})
    usage.dump(out / "usage.json")
    _write(out / "REVIEW.md", build_review_md(brief, plan, results, review, cfg, run_id, files))

    ready = all(r.ok for r in results.values()) and (
        review is None or all(p in review.platforms and review.platforms[p].ready_to_post for p in results))
    return RunPackage(run_id, out, ready)


def batch_summary(packages: list[tuple[Brief, RunPackage]], output_root: Path,
                  failed: list[str] | None = None) -> Path:
    L = ["# BATCH SUMMARY", "", "| brief | run | mode | platforms | status |", "|---|---|---|---|---|"]
    for brief, pkg in packages:
        rel = pkg.out_dir.relative_to(output_root)
        L.append(f"| {Path(brief.source_path).name} | [{pkg.run_id}]({rel}/REVIEW.md) | {brief.mode} | "
                 f"{', '.join(brief.platforms)} | {'✅' if pkg.ready else '⚠️ check REVIEW.md'} |")
    for f in failed or []:
        L.append(f"| {f.split(':', 1)[0]} | — | — | — | ❌ {f.split(':', 1)[1].strip()} |")
    path = output_root / f"BATCH_SUMMARY_{re.sub(r'[^0-9]', '', date.today().isoformat())}.md"
    _write(path, "\n".join(L) + "\n")
    return path
