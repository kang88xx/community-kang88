from pathlib import Path

import pytest

from community_agent.brief import load_brief
from community_agent.config import load_config
from community_agent.schemas import LinkedInPost, RedditPost, TelegramPost, Tweet, XPost
from community_agent.validate import errors_only, validate_post, x_weighted_length

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def brief():
    return load_brief(ROOT / "brief.example.md")


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_x_weighted_length():
    assert x_weighted_length("hello") == 5
    assert x_weighted_length("see https://example.com/a/very/long/path/that/goes/on") == 4 + 23
    assert x_weighted_length("한글") == 4
    assert x_weighted_length("🚀") == 2
    assert x_weighted_length("❤️") == 2          # VS16
    assert x_weighted_length("👨‍👩‍👧") == 2       # ZWJ family
    assert x_weighted_length("👍🏽") == 2          # skin tone
    assert x_weighted_length("🇰🇷") == 2          # flag pair
    assert x_weighted_length("1️⃣") == 1          # keycap on a digit (digit=1, modifiers 0)
    assert x_weighted_length("é") == x_weighted_length("e\u0301")  # NFC


def test_telegram_counts_rendered_text(brief, cfg):
    # 1,000 visible chars wrapped in tags is fine; raw length would exceed the 1024 caption limit.
    body = "가" * 1000
    post = TelegramPost(text_html=f"<b>{body}</b> <a href=\"https://example.com/release\">https://example.com/release</a> &amp; done",
                        caption_html=f"<b>{body}</b> <a href=\"https://x.y/z\">link</a>", text_plain=body)
    v = errors_only(validate_post("telegram", post, brief, cfg))
    assert v == [], [x.message for x in v]


def test_x_over_280_and_hashtags(brief, cfg):
    post = XPost(tweets=[Tweet(text="a" * 281), Tweet(text="ok #one #two #three https://x.y https://z.w")], hashtags=[])
    rules = {v.rule for v in errors_only(validate_post("x", post, brief, cfg))}
    assert {"max_chars", "hashtag_count", "link_count"} <= rules


def test_x_valid_thread(brief, cfg):
    post = XPost(tweets=[Tweet(text="Latency 50ms -> 12ms after swapping the CRDT engine."),
                         Tweet(text="Star it on GitHub: https://github.com/example/repo #crdt")])
    assert errors_only(validate_post("x", post, brief, cfg)) == []


def test_avoid_phrase_detected(brief, cfg):
    post = LinkedInPost(text="This is a 혁명적 change.\n\nBody.\n\n#A #B #C", first_comment="https://example.com/release")
    rules = [v.rule for v in errors_only(validate_post("linkedin", post, brief, cfg))]
    assert "avoid_phrase" in rules


def test_linkedin_rules(brief, cfg):
    post = LinkedInPost(text="Hook line.\n\nBody with a link https://example.com\n\n#One #Two", first_comment="")
    v = validate_post("linkedin", post, brief, cfg)
    rules = {x.rule for x in errors_only(v)}
    assert {"link_count", "hashtag_count"} <= rules
    assert any(x.rule == "link_missing" and x.severity == "warn" for x in v)


def test_reddit_rules(brief, cfg):
    post = RedditPost(title="We cut sync latency from 50ms to 12ms #crdt", body_markdown="https://a.b first\n\nthen body text that is longer" * 3)
    rules = {x.rule for x in errors_only(validate_post("reddit", post, brief, cfg))}
    assert "hashtag_count" in rules
    assert "link_count" in rules  # 3 links > 2


def test_telegram_rules(brief, cfg):
    post = TelegramPost(text_html="<b>Hi</b> <div>bad</div>", caption_html="x" * 1025, text_plain="Hi bad")
    rules = {x.rule for x in errors_only(validate_post("telegram", post, brief, cfg))}
    assert {"html_tags", "caption_max_chars"} <= rules


def test_language_warning_only(brief, cfg):
    post = RedditPost(title="제목", body_markdown="한국어로만 쓴 본문입니다. 레딧은 영어를 기대합니다.")
    v = validate_post("reddit", post, brief, cfg)
    lang = [x for x in v if x.rule == "language"]
    assert lang and lang[0].severity == "warn"
