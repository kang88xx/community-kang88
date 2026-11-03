"""Structured-output schemas must be what the API accepts, and the real request must be well-formed.

The second test sends a real AnthropicLLM call through an httpx2 MockTransport, so no network/key.
"""
import json

import httpx2 as httpx
import pytest
from anthropic import Anthropic

from community_agent.llm import FALLBACK_BETA, AnthropicLLM, RefusedError
from community_agent.schemas import POST_MODELS, PlanOut, RedditPost, ReviewOut, strict_schema

LLM_MODELS = [PlanOut, ReviewOut, *POST_MODELS.values()]


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


@pytest.mark.parametrize("model", LLM_MODELS, ids=lambda m: m.__name__)
def test_schema_is_strict(model):
    schema = strict_schema(model)
    for node in _walk(schema):
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False, node
            assert "properties" in node, "dict[str, X] fields are not allowed in LLM-facing models"
        for k in ("minimum", "maximum", "default"):
            assert k not in node, (k, node)


def test_reddit_schema_keeps_title_property():
    props = strict_schema(RedditPost)["properties"]
    assert "title" in props and props["title"]["type"] == "string"


def _fake_api(payload_sink, body_text, stop_reason="end_turn", stop_details=None):
    def handler(request: httpx.Request) -> httpx.Response:
        payload_sink.append({"headers": dict(request.headers), "json": json.loads(request.content)})
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": body_text}], "stop_reason": stop_reason,
            "stop_details": stop_details, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
        })
    return handler


def test_real_request_shape():
    sent = []
    client = Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(
        _fake_api(sent, json.dumps({"title": "T", "body_markdown": "B", "suggested_subreddits": [], "flair": "", "post_type": "text", "notes": ""})))))
    llm = AnthropicLLM(client=client)
    post = llm.generate(stage="t", system=["shared", "platform", "rules"], user="hi", schema=RedditPost)
    assert post.title == "T"
    req = sent[0]
    assert FALLBACK_BETA in req["headers"]["anthropic-beta"]
    body = req["json"]
    assert body["fallbacks"] == "default"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["output_config"]["effort"] == "high"
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert body["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "thinking" not in body  # adaptive by default on claude-opus-5-5
    assert llm.usage.records[0].input_tokens == 10


def test_refusal_raises():
    sent = []
    client = Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(
        _fake_api(sent, "", stop_reason="refusal", stop_details={"type": "refusal", "category": "cyber", "explanation": "x"}))))
    with pytest.raises(RefusedError):
        AnthropicLLM(client=client).generate(stage="t", system=["s"], user="u", schema=RedditPost)
