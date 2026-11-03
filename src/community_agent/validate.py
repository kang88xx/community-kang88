"""Validator — hard platform constraints enforced by code, never by the LLM.

Returns a list of Violation; `severity="error"` triggers a Writer retry, `"warn"` is only reported.
Violations are serialised as-is into the retry prompt (`validation_errors`).
"""
from __future__ import annotations

import html as _html
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import BaseModel

from .brief import Brief
from .config import Config

URL_RE = re.compile(r"https?://[^\s<>()\"']+|(?<![\w@])www\.[^\s<>()\"']+")
HASHTAG_RE = re.compile(r"(?<![\w&])#([\w가-힣]+)")
HTML_TAG_RE = re.compile(r"<\s*/?\s*([a-zA-Z0-9]+)[^>]*>")
TELEGRAM_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "a", "tg-spoiler", "blockquote", "br"}
HANGUL_RE = re.compile(r"[가-힣]")
LATIN_RE = re.compile(r"[A-Za-z]")


@dataclass
class Violation:
    rule: str
    field: str
    actual: Any
    limit: Any
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- length helpers


def x_weighted_length(text: str) -> int:
    """twitter-text style length: URLs count 23, most Latin/punctuation 1, CJK 2, any emoji
    sequence (ZWJ family, skin tone, flag, keycap, variation selector) 2. NFC-normalised first."""
    text = unicodedata.normalize("NFC", text)
    total = 0
    pos = 0
    for m in URL_RE.finditer(text):
        total += _weight(text[pos:m.start()])
        total += 23
        pos = m.end()
    total += _weight(text[pos:])
    return total


_ZWJ = 0x200D
_VS16 = 0xFE0F
_KEYCAP = 0x20E3
_SKIN = range(0x1F3FB, 0x1F400)
_REGIONAL = range(0x1F1E6, 0x1F200)
_TAGS = range(0xE0020, 0xE0080)  # subdivision-flag tag sequences


def _weight(s: str) -> int:
    w = 0
    skip_next = False  # codepoint after a ZWJ belongs to the same emoji sequence
    pending_flag = False
    for ch in s:
        cp = ord(ch)
        if cp == _ZWJ:
            skip_next = True
            continue
        if cp == _VS16 or cp == _KEYCAP or cp in _SKIN or cp in _TAGS:
            continue  # modifies the previous codepoint; no extra weight
        if skip_next:
            skip_next = False
            continue
        if cp in _REGIONAL:  # a flag is a pair; twitter counts the pair as 2
            if pending_flag:
                pending_flag = False
                continue
            pending_flag = True
            w += 2
            continue
        pending_flag = False
        if (0 <= cp <= 4351) or (8192 <= cp <= 8205) or (8208 <= cp <= 8223) or (8242 <= cp <= 8247):
            w += 1
        else:
            w += 2
    return w


HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.I)


def strip_html(text: str) -> str:
    """Telegram counts limits on the rendered text: tags removed, entities unescaped."""
    return _html.unescape(HTML_TAG_RE.sub("", text))


def codepoints(text: str) -> int:
    return len(text)


def detect_language(text: str) -> str:
    """'ko' if Hangul is a meaningful share of letters, else 'en'. Crude but enough for a warning."""
    ko = len(HANGUL_RE.findall(text))
    en = len(LATIN_RE.findall(text))
    if ko == 0 and en == 0:
        return "unknown"
    return "ko" if ko / max(ko + en, 1) > 0.2 else "en"


def hashtags_in(text: str) -> list[str]:
    return HASHTAG_RE.findall(text)


def urls_in(text: str) -> list[str]:
    return URL_RE.findall(text)


# --------------------------------------------------------------------------- shared rules


def _check_avoid(text: str, field: str, brief: Brief) -> list[Violation]:
    out = []
    norm = re.sub(r"\s+", "", text.lower())
    for phrase in brief.avoid:
        p = re.sub(r"\s+", "", phrase.lower())
        if p and p in norm:
            out.append(Violation("avoid_phrase", field, phrase, "forbidden",
                                 f"Contains forbidden expression '{phrase}' — rephrase without it."))
    return out


def _check_language(text: str, field: str, expected: list[str]) -> list[Violation]:
    if not text.strip():
        return []
    got = detect_language(text)
    if got != "unknown" and got not in expected:
        return [Violation("language", field, got, expected,
                          f"Text reads as '{got}' but platform expects {expected}.", severity="warn")]
    return []


def _check_hashtags(count: int, field: str, rule: dict[str, int]) -> list[Violation]:
    lo, hi = rule.get("min", 0), rule.get("max", 99)
    if count < lo or count > hi:
        return [Violation("hashtag_count", field, count, f"{lo}-{hi}",
                          f"{count} hashtags; platform allows {lo}-{hi}.")]
    return []


def _check_links(count: int, field: str, max_links: int, severity: str = "error") -> list[Violation]:
    if count > max_links:
        return [Violation("link_count", field, count, max_links,
                          f"{count} links; platform allows at most {max_links}.", severity=severity)]
    return []


# --------------------------------------------------------------------------- per platform


def validate_telegram(post: Any, brief: Brief, rules: dict[str, Any]) -> list[Violation]:
    t = rules["text"]
    v: list[Violation] = []
    n = codepoints(strip_html(post.text_html))
    if n > t["max_chars"]:
        v.append(Violation("max_chars", "text_html", n, t["max_chars"], f"text_html renders to {n} chars; max {t['max_chars']}."))
    c = codepoints(strip_html(post.caption_html))
    if c > t["caption_max_chars"]:
        v.append(Violation("caption_max_chars", "caption_html", c, t["caption_max_chars"],
                           f"caption_html renders to {c} chars; max {t['caption_max_chars']} (media caption limit)."))
    if not post.caption_html.strip():
        v.append(Violation("required", "caption_html", 0, ">0", "caption_html is empty; it must stand alone under media."))
    for field in ("text_html", "caption_html"):
        raw = getattr(post, field)
        bad = {tag.lower() for tag in HTML_TAG_RE.findall(raw)} - TELEGRAM_TAGS
        if bad:
            v.append(Violation("html_tags", field, sorted(bad), sorted(TELEGRAM_TAGS),
                               f"Unsupported HTML tags {sorted(bad)}; Telegram allows only {sorted(TELEGRAM_TAGS)}."))
        visible = strip_html(raw)
        hrefs = set(HREF_RE.findall(raw))
        bare = {u for u in urls_in(visible) if u not in hrefs}
        v += _check_hashtags(len(hashtags_in(visible)), field, t["hashtags"])
        v += _check_links(len(hrefs | bare), field, t["max_links"])
        v += _check_avoid(visible, field, brief)
    v += _check_language(post.text_plain, "text_plain", brief.languages_for("telegram", rules.get("language")))
    return v


def validate_x(post: Any, brief: Brief, rules: dict[str, Any]) -> list[Violation]:
    t = rules["text"]
    v: list[Violation] = []
    n_tweets = len(post.tweets)
    th = t["thread"]
    if n_tweets < th["min_tweets"] or n_tweets > th["max_tweets"]:
        v.append(Violation("thread_length", "tweets", n_tweets, f"{th['min_tweets']}-{th['max_tweets']}",
                           f"{n_tweets} tweets; allowed {th['min_tweets']}-{th['max_tweets']}."))
    total_tags = 0
    total_links = 0
    for i, tw in enumerate(post.tweets):
        field = f"tweets[{i}].text"
        n = x_weighted_length(tw.text)
        if n > t["max_chars"]:
            v.append(Violation("max_chars", field, n, t["max_chars"],
                               f"Tweet {i + 1} is {n} weighted chars (URLs=23, CJK/emoji=2); max {t['max_chars']}."))
        if not tw.text.strip():
            v.append(Violation("required", field, 0, ">0", f"Tweet {i + 1} is empty."))
        tags = hashtags_in(tw.text)
        total_tags += len(tags)
        if tags and i != n_tweets - 1 and n_tweets > 1:
            v.append(Violation("hashtag_position", field, tags, "last tweet only",
                               f"Hashtags in tweet {i + 1}; put them only in the last tweet.", severity="warn"))
        links = urls_in(tw.text)
        total_links += len(links)
        if links and i == 0 and n_tweets > 1:
            v.append(Violation("link_position", field, links, "not in hook",
                               "Link in the hook tweet of a thread; move it to the last tweet.", severity="warn"))
        v += _check_avoid(tw.text, field, brief)
        v += _check_language(tw.text, field, brief.languages_for("x", rules.get("language")))
    v += _check_hashtags(total_tags, "tweets", t["hashtags"])
    v += _check_links(total_links, "tweets", t["max_links"])
    if len(post.alt_text) > t["alt_text_max_chars"]:
        v.append(Violation("alt_text_max_chars", "alt_text", len(post.alt_text), t["alt_text_max_chars"],
                           "alt_text too long.", severity="warn"))
    return v


def validate_reddit(post: Any, brief: Brief, rules: dict[str, Any]) -> list[Violation]:
    t = rules["text"]
    v: list[Violation] = []
    n = codepoints(post.title)
    if n > t["title_max_chars"]:
        v.append(Violation("title_max_chars", "title", n, t["title_max_chars"], f"Title is {n} chars; max {t['title_max_chars']}."))
    if not post.title.strip():
        v.append(Violation("required", "title", 0, ">0", "Title is empty."))
    b = codepoints(post.body_markdown)
    if b > t["body_max_chars"]:
        v.append(Violation("body_max_chars", "body_markdown", b, t["body_max_chars"], f"Body is {b} chars; max {t['body_max_chars']}."))
    for field in ("title", "body_markdown"):
        tags = hashtags_in(getattr(post, field))
        if tags:
            v.append(Violation("hashtag_count", field, len(tags), 0, f"Hashtags {tags} are not used on Reddit; remove them."))
        v += _check_avoid(getattr(post, field), field, brief)
    links = urls_in(post.body_markdown)
    v += _check_links(len(links), "body_markdown", t["max_links"])
    if links and t.get("link_position") == "bottom":
        first_link_at = post.body_markdown.find(links[0])
        if first_link_at < len(post.body_markdown) * 0.6:
            v.append(Violation("link_position", "body_markdown", "early", "bottom",
                               "External links should sit at the bottom of the body.", severity="warn"))
    v += _check_language(post.body_markdown, "body_markdown", brief.languages_for("reddit", rules.get("language")))
    return v


def validate_linkedin(post: Any, brief: Brief, rules: dict[str, Any]) -> list[Violation]:
    t = rules["text"]
    v: list[Violation] = []
    n = codepoints(post.text)
    if n > t["max_chars"]:
        v.append(Violation("max_chars", "text", n, t["max_chars"], f"Text is {n} chars; max {t['max_chars']}."))
    hook = post.text.strip().split("\n\n", 1)[0]
    if len(hook) > t["hook_max_chars"]:
        v.append(Violation("hook_max_chars", "text", len(hook), t["hook_max_chars"],
                           f"Hook (text before the first blank line) is {len(hook)} chars; keep it under {t['hook_max_chars']} so it shows before 'see more'.",
                           severity="warn"))
    v += _check_hashtags(len(hashtags_in(post.text)), "text", t["hashtags"])
    v += _check_links(len(urls_in(post.text)), "text", t["max_links"])
    fc = codepoints(post.first_comment)
    if fc > t["first_comment_max_chars"]:
        v.append(Violation("first_comment_max_chars", "first_comment", fc, t["first_comment_max_chars"],
                           f"first_comment is {fc} chars; max {t['first_comment_max_chars']}."))
    if brief.links and not urls_in(post.first_comment):
        v.append(Violation("link_missing", "first_comment", 0, ">=1",
                           "Brief has links but first_comment contains none; put the link there.", severity="warn"))
    if len(post.alt_text) > t["alt_text_max_chars"]:
        v.append(Violation("alt_text_max_chars", "alt_text", len(post.alt_text), t["alt_text_max_chars"],
                           "alt_text too long.", severity="warn"))
    v += _check_avoid(post.text, "text", brief)
    v += _check_language(post.text, "text", brief.languages_for("linkedin", rules.get("language")))
    return v


VALIDATORS = {
    "telegram": validate_telegram,
    "x": validate_x,
    "reddit": validate_reddit,
    "linkedin": validate_linkedin,
}


def validate_post(platform: str, post: BaseModel, brief: Brief, cfg: Config) -> list[Violation]:
    return VALIDATORS[platform](post, brief, cfg.platform(platform))


def errors_only(violations: list[Violation]) -> list[Violation]:
    return [v for v in violations if v.severity == "error"]
