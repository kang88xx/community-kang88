"""`community` CLI.

  community run briefs/x.md                     campaign (all platforms in the brief) or single
  community run briefs/x.md --platform x,reddit  subset
  community run briefs/*.md                     batch -> BATCH_SUMMARY_<date>.md
  community run ... --dry-run                   no API calls (MockLLM), exercises the whole pipeline
  community validate output/<run_id>            re-run the validator on an existing run
"""
from __future__ import annotations

import argparse
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .brief import Brief, load_brief
from .config import PLATFORMS, load_config
from .llm import LLM, MODEL_REVIEW, MODEL_WRITE, AnthropicLLM, MockLLM
from .package import RunPackage, batch_summary, package_run
from .paths import OUTPUT_DIR, ROOT
from .planner import make_plan
from .reviewer import review_posts
from .writers.base import WriterResult, write_post

console = Console()


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal KEY=VALUE loader for the gitignored .env (never overrides existing env)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def run_brief(brief: Brief, llm: LLM, *, output_root: Path, do_review: bool = True,
              model: str = MODEL_WRITE, review_model: str = MODEL_REVIEW, max_retries: int = 2) -> RunPackage:
    cfg = load_config()
    console.print(f"[bold]{brief.title}[/] — {brief.mode} · {', '.join(brief.platforms)}")

    console.print("  ① planner …", end=" ")
    plan = make_plan(llm, brief, cfg, model=model)
    console.print("done")

    console.print(f"  ② writers ×{len(brief.platforms)} (parallel) …", end=" ")
    with ThreadPoolExecutor(max_workers=len(brief.platforms)) as pool:
        futures = {p: pool.submit(write_post, llm, p, brief, plan, cfg, model, max_retries) for p in brief.platforms}
        results: dict[str, WriterResult] = {p: f.result() for p, f in futures.items()}
    console.print(" ".join(f"{p}:{'ok' if r.ok else 'FAIL'}({r.attempts})" for p, r in results.items()))

    review = None
    if do_review:
        console.print("  ⑥ reviewer …", end=" ")
        review = review_posts(llm, brief, plan, results, cfg, model=review_model)
        console.print("done")

    pkg = package_run(brief, plan, results, review, llm.usage, cfg, output_root)
    console.print(f"  ⑦ packaged → [cyan]{pkg.out_dir.relative_to(ROOT) if pkg.out_dir.is_relative_to(ROOT) else pkg.out_dir}[/]"
                  f"  {'✅ ready' if pkg.ready else '⚠️ needs attention (see REVIEW.md)'}")
    return pkg


def cmd_run(args: argparse.Namespace) -> int:
    load_dotenv()
    llm: LLM = MockLLM() if args.dry_run else AnthropicLLM()
    output_root = Path(args.out) if args.out else OUTPUT_DIR
    platform_override = [p.strip() for p in args.platform.split(",")] if args.platform else None
    if platform_override:
        bad = [p for p in platform_override if p not in PLATFORMS]
        if bad:
            console.print(f"[red]unknown platform(s): {bad}[/]")
            return 2

    packages: list[tuple[Brief, RunPackage]] = []
    failed: list[str] = []
    for path in args.briefs:
        try:
            brief = load_brief(path)
            if platform_override:
                brief = brief.model_copy(update={"platforms": platform_override})
            pkg = run_brief(brief, llm, output_root=output_root, do_review=not args.no_review,
                            model=args.model, review_model=args.review_model, max_retries=args.max_retries)
            packages.append((brief, pkg))
        except Exception as exc:  # keep the batch going; report at the end
            failed.append(f"{path}: {type(exc).__name__}: {exc}")
            console.print(f"[red]✗ {path} failed: {type(exc).__name__}: {exc}[/]")
            if len(args.briefs) == 1:
                traceback.print_exc()

    if len(args.briefs) > 1:
        summary = batch_summary(packages, output_root, failed)
        console.print(f"\nbatch summary → [cyan]{summary}[/]")

    totals = llm.usage.totals()
    console.print(f"\nusage: in {totals['input_tokens']} · out {totals['output_tokens']} · "
                  f"cache read {totals['cache_read_input_tokens']} · cache write {totals['cache_creation_input_tokens']}")
    return 0 if packages and not failed and all(p.ready for _, p in packages) else 1


def cmd_validate(args: argparse.Namespace) -> int:
    import json

    from .schemas import POST_MODELS
    from .validate import validate_post

    cfg = load_config()
    run_dir = Path(args.run_dir)
    brief = load_brief(run_dir / "brief.md")
    table = Table("platform", "severity", "rule", "field", "message")
    exit_code = 0
    for p in PLATFORMS:
        f = run_dir / p / "post.json"
        if not f.exists():
            continue
        post = POST_MODELS[p].model_validate(json.loads(f.read_text(encoding="utf-8")))
        for v in validate_post(p, post, brief, cfg):
            table.add_row(p, v.severity, v.rule, v.field, v.message)
            if v.severity == "error":
                exit_code = 1
    console.print(table if table.row_count else "[green]no violations[/]")
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="community", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="generate posts from one or more briefs")
    r.add_argument("briefs", nargs="+", help="brief .md file(s)")
    r.add_argument("--platform", help="comma-separated subset, e.g. x,reddit")
    r.add_argument("--dry-run", action="store_true", help="no API calls; MockLLM")
    r.add_argument("--no-review", action="store_true", help="skip the Reviewer step")
    r.add_argument("--model", default=MODEL_WRITE, help=f"writer/planner model (default {MODEL_WRITE})")
    r.add_argument("--review-model", default=MODEL_REVIEW, help=f"reviewer model (default {MODEL_REVIEW})")
    r.add_argument("--max-retries", type=int, default=2, help="validator-driven rewrite attempts per platform")
    r.add_argument("--out", help="output root (default ./output)")
    r.set_defaults(func=cmd_run)

    v = sub.add_parser("validate", help="re-run the validator on an existing output/<run_id>")
    v.add_argument("run_dir")
    v.set_defaults(func=cmd_validate)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
