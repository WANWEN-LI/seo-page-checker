import json
from types import SimpleNamespace

from seo_checker import ai_suggest, report
from tests.test_history_report import make_report


class FakeMessages:
    def __init__(self, text, stop_reason="end_turn"):
        self.text, self.stop_reason, self.kwargs = text, stop_reason, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(stop_reason=self.stop_reason, model="claude-opus-5-5",
                               content=[SimpleNamespace(type="text", text=self.text)],
                               usage=SimpleNamespace(input_tokens=100, output_tokens=50))


def fake_client(payload, stop_reason="end_turn"):
    msgs = FakeMessages(json.dumps(payload) if isinstance(payload, dict) else payload, stop_reason)
    return SimpleNamespace(beta=SimpleNamespace(messages=msgs)), msgs


GOOD = {
    "title_options": [{"text": "  About Wanwen Li |  Marketing Analytics  ", "rationale": "r"},
                      {"text": "Hi", "rationale": "too short"}],
    "description_options": [{"text": "x" * 120, "rationale": "r"}],
    "top_fixes": [
        {"check_id": "json_ld", "title": "Add JSON-LD", "impact": "Medium", "effort": "Low", "evidence": "e", "action": "a"},
        {"check_id": "cta_fold", "title": "Add CTA", "impact": "High", "effort": "Medium", "evidence": "e", "action": "a"},
        {"check_id": "made_up", "title": "Invented", "impact": "High", "effort": "Low", "evidence": "e", "action": "a"},
        {"check_id": "json_ld", "title": "Duplicate", "impact": "High", "effort": "Low", "evidence": "e", "action": "a"},
    ],
}


def test_skipped_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = ai_suggest.suggest(make_report())
    assert r == {"enabled": False, "ok": False, "error": "ANTHROPIC_API_KEY not set; AI suggestions skipped."}


def test_grounding_char_counts_and_ranking():
    client, msgs = fake_client(GOOD)
    r = ai_suggest.suggest(make_report(), client=client)
    assert r["ok"]
    assert [f["check_id"] for f in r["fixes"]] == ["json_ld", "cta_fold"]  # invented id dropped, duplicate removed
    assert r["dropped_fixes"] == 1
    assert r["fixes"][0]["priority"] == 2.0 and r["fixes"][1]["priority"] == 1.5
    t = r["titles"][0]
    assert t["text"] == "About Wanwen Li | Marketing Analytics" and t["chars"] == len(t["text"]) and t["in_range"]
    assert r["titles"][1]["in_range"] is False
    # request shape: default model, fallbacks opted in, structured output
    assert msgs.kwargs["model"] == "claude-opus-5-5"
    assert msgs.kwargs["fallbacks"] == "default" and msgs.kwargs["betas"] == ["server-side-fallback-2026-07-01"]
    assert msgs.kwargs["output_config"]["format"]["type"] == "json_schema"


def test_payload_contains_only_failing_checks():
    payload = ai_suggest.build_payload(make_report())
    assert {i["check_id"] for i in payload["issues"]} == {"canonical", "json_ld", "cta_fold"}


def test_refusal_and_bad_json_are_reported():
    client, _ = fake_client(GOOD, stop_reason="refusal")
    assert ai_suggest.suggest(make_report(), client=client)["error"] == "The model declined this request."
    client, _ = fake_client("not json")
    assert "not valid JSON" in ai_suggest.suggest(make_report(), client=client)["error"]


def test_ai_section_rendered_and_escaped():
    client, _ = fake_client({**GOOD, "title_options": [{"text": "<b>x</b>", "rationale": "r"}]})
    r = make_report()
    r["ai"] = ai_suggest.suggest(r, client=client)
    html = report.render_html(r)
    assert "AI suggestions" in html and "&lt;b&gt;x&lt;/b&gt;" in html
