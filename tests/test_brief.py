from pathlib import Path

from community_agent.brief import load_brief, slugify

ROOT = Path(__file__).resolve().parents[1]


def test_example_brief_parses():
    b = load_brief(ROOT / "brief.example.md")
    assert b.slug == "v2-release"
    assert b.mode == "campaign"
    assert b.platforms == ["telegram", "x", "reddit", "linkedin"]
    assert b.languages_for("reddit") == ["en"]
    assert b.languages_for("telegram") == ["ko"]
    assert b.media_for("x") == ["jpg", "gif"]
    assert b.media_for("reddit") == ["jpg"]  # default
    assert "혁명적" in b.avoid and "업계 최초" in b.avoid and "경쟁사 직접 언급" in b.avoid
    assert "reddit" in b.platform_notes and "linkedin" in b.platform_notes
    assert b.reddit.subreddits == ["r/webdev", "r/SideProject"]
    assert b.links[1].url.startswith("https://github.com")


def test_single_mode_and_slug(tmp_path):
    p = tmp_path / "x-tip.md"
    p.write_text("---\ntitle: 'Tip'\nplatforms: [x]\n---\n- one line\n", encoding="utf-8")
    b = load_brief(p)
    assert b.mode == "single"
    assert b.slug == "x-tip"
    assert b.languages_for("x", ["en"]) == ["en"]  # no language in brief -> platforms.yaml wins
    assert b.languages_for("x") == ["ko"]


def test_language_precedence(tmp_path):
    p = tmp_path / "b.md"
    p.write_text("---\ntitle: T\nlanguage: {default: [ko], reddit: [en]}\n---\nbody\n", encoding="utf-8")
    b = load_brief(p)
    assert b.languages_for("reddit", ["en"]) == ["en"]
    assert b.languages_for("linkedin", ["en"]) == ["ko"]  # explicit brief default beats yaml


def test_slug_is_sanitised(tmp_path):
    p = tmp_path / "b.md"
    p.write_text("---\ntitle: T\nslug: '../escape'\n---\nbody\n", encoding="utf-8")
    assert load_brief(p).slug == "escape"


def test_slugify():
    assert slugify("Hello, World! v2.0") == "hello-world-v2-0"
    assert slugify("한글 제목 테스트") == "한글-제목-테스트"
