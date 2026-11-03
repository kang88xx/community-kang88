import json
from pathlib import Path

from community_agent.brief import load_brief
from community_agent.cli import main, run_brief
from community_agent.llm import MockLLM

ROOT = Path(__file__).resolve().parents[1]


def test_dry_run_campaign(tmp_path):
    brief = load_brief(ROOT / "brief.example.md")
    llm = MockLLM()
    pkg = run_brief(brief, llm, output_root=tmp_path)
    assert pkg.ready
    out = pkg.out_dir
    assert out.name.endswith("_v2-release")
    for f in ("REVIEW.md", "plan.json", "review.json", "usage.json", "validation.json", "brief.md"):
        assert (out / f).exists(), f
    assert (out / "x" / "thread.txt").exists()
    assert (out / "linkedin" / "first_comment.txt").exists()
    assert (out / "telegram" / "caption.html").exists()
    assert (out / "reddit" / "post.md").exists()
    stages = [c["stage"] for c in llm.calls]
    assert stages[0] == "planner" and stages[-1] == "reviewer"
    assert sum(s.startswith("writer:") for s in stages) == 4
    review_md = (out / "REVIEW.md").read_text(encoding="utf-8")
    assert "## telegram" in review_md and "## linkedin" in review_md
    usage = json.loads((out / "usage.json").read_text())
    assert len(usage["calls"]) == 6


def test_dry_run_single_cli(tmp_path):
    p = tmp_path / "tip.md"
    p.write_text("---\ntitle: 'git worktree tip'\nslug: x-tip-1\nplatforms: [x]\nlanguage: [en]\ncta: 'Try it'\n---\n- one liner\n", encoding="utf-8")
    code = main(["run", str(p), "--dry-run", "--no-review", "--out", str(tmp_path / "out")])
    assert code == 0
    runs = list((tmp_path / "out").iterdir())
    assert len(runs) == 1 and runs[0].name.endswith("_x-tip-1_x")
    assert not (runs[0] / "review.json").exists()
    assert (runs[0] / "x" / "post.json").exists()
    assert not (runs[0] / "telegram").exists()


def test_batch_and_platform_override(tmp_path):
    a = tmp_path / "a.md"; a.write_text("---\ntitle: A\nslug: a\n---\nbody\n", encoding="utf-8")
    b = tmp_path / "b.md"; b.write_text("---\ntitle: B\nslug: b\n---\nbody\n", encoding="utf-8")
    code = main(["run", str(a), str(b), "--dry-run", "--platform", "x,reddit", "--out", str(tmp_path / "out")])
    assert code == 0
    summaries = list((tmp_path / "out").glob("BATCH_SUMMARY_*.md"))
    assert len(summaries) == 1
    for run in (tmp_path / "out").iterdir():
        if run.is_dir():
            assert (run / "x").exists() and (run / "reddit").exists() and not (run / "linkedin").exists()


def test_writer_failure_still_packages(tmp_path):
    from community_agent.llm import RefusedError
    brief = load_brief(ROOT / "brief.example.md").model_copy(update={"platforms": ["x", "reddit"]})
    llm = MockLLM(fail_stages={"writer:x#1": RefusedError("nope"), "writer:x#2": RuntimeError("max_tokens"),
                               "writer:x#3": ValueError("bad json")})
    pkg = run_brief(brief, llm, output_root=tmp_path)
    assert not pkg.ready
    val = json.loads((pkg.out_dir / "validation.json").read_text(encoding="utf-8"))
    assert val["x"]["ok"] is False and val["x"]["attempts"] == 3
    assert val["x"]["history"][0]["errors"][0]["rule"] == "llm_error"
    assert val["reddit"]["ok"] is True
    assert (pkg.out_dir / "x" / "post.json").exists()  # empty placeholder, still packaged
    assert "llm_error" in (pkg.out_dir / "REVIEW.md").read_text(encoding="utf-8")


def test_no_silent_overwrite(tmp_path):
    brief = load_brief(ROOT / "brief.example.md").model_copy(update={"platforms": ["x"]})
    a = run_brief(brief, MockLLM(), output_root=tmp_path, do_review=False)
    b = run_brief(brief, MockLLM(), output_root=tmp_path, do_review=False)
    assert a.out_dir != b.out_dir and b.out_dir.name == a.out_dir.name + "-2"


def test_batch_continues_after_bad_brief(tmp_path):
    good = tmp_path / "good.md"; good.write_text("---\ntitle: G\nslug: g\nplatforms: [x]\n---\nbody\n", encoding="utf-8")
    bad = tmp_path / "bad.md"; bad.write_text("---\ntitle: B\nplatforms: [myspace]\n---\nbody\n", encoding="utf-8")
    code = main(["run", str(bad), str(good), "--dry-run", "--out", str(tmp_path / "out")])
    assert code == 1
    summary = next((tmp_path / "out").glob("BATCH_SUMMARY_*.md")).read_text(encoding="utf-8")
    assert "❌" in summary and "g_x" in summary
