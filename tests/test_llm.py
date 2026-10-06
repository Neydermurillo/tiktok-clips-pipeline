import json
from types import SimpleNamespace

import pytest

from clips import gemini_client, llm, scoring
from clips.claude_client import ClipScore

GOOD = json.dumps({"score": 80, "title": "Título", "hook": "Gancho", "hashtags": ["#ia"]})


def _resp(text=GOOD):
    return SimpleNamespace(text=text, usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=20))


class FakeAPIError(Exception):
    def __init__(self, code):
        super().__init__(f"error {code}")
        self.code = code


def _setup(monkeypatch, outcomes):
    calls, logged = [], []

    class Models:
        def generate_content(self, **kw):
            calls.append(kw)
            out = outcomes.pop(0)
            if isinstance(out, Exception):
                raise out
            return out

    monkeypatch.setattr(gemini_client, "_client", lambda: SimpleNamespace(models=Models()))
    monkeypatch.setattr(gemini_client.time, "sleep", lambda s: None)
    monkeypatch.setenv("GEMINI_MIN_INTERVAL_S", "0")
    monkeypatch.setattr(gemini_client.db, "execute", lambda sql, params=None: logged.append(params))
    return calls, logged


# ---------- selección de proveedor ----------
def test_provider_default_is_none(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("USE_CLAUDE", raising=False)
    assert llm.provider() == "none"


def test_provider_legacy_use_claude(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("USE_CLAUDE", "true")
    assert llm.provider() == "claude"


def test_provider_explicit_and_invalid(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert llm.provider() == "gemini"
    monkeypatch.setenv("LLM_PROVIDER", "otro")
    with pytest.raises(ValueError):
        llm.provider()


# ---------- cliente Gemini ----------
def test_gemini_score_parses_and_logs_usage(monkeypatch):
    calls, logged = _setup(monkeypatch, [_resp()])
    monkeypatch.setenv("GEMINI_MODEL", "modelo-x")
    res = gemini_client.score_segment("texto")
    assert (res.score, res.title) == (80, "Título")
    assert logged == [("score_segment", "gemini:modelo-x", 10, 20)]
    assert calls[0]["config"].response_mime_type == "application/json"


def test_gemini_retries_on_429(monkeypatch):
    calls, _ = _setup(monkeypatch, [FakeAPIError(429), _resp()])
    assert gemini_client.score_segment("t").score == 80
    assert len(calls) == 2


def test_gemini_does_not_retry_client_errors(monkeypatch):
    calls, _ = _setup(monkeypatch, [FakeAPIError(400), _resp()])
    with pytest.raises(FakeAPIError):
        gemini_client.score_segment("t")
    assert len(calls) == 1


def test_gemini_empty_response_raises(monkeypatch):
    _setup(monkeypatch, [_resp(text=None)])
    with pytest.raises(ValueError):
        gemini_client.score_segment("t")


# ---------- scoring con y sin proveedor ----------
def _patch_scoring(monkeypatch):
    updates = []

    def query(sql, params=None):
        if "FROM videos" in sql:
            return [{"id": 1}]
        return [{"id": i, "text": f"Frase {i}. Otra frase.", "duration": 30.0} for i in range(1, 4)]

    monkeypatch.setattr(scoring.db, "query", query)
    monkeypatch.setattr(scoring.db, "execute", lambda sql, params=None: updates.append((sql, params)))
    monkeypatch.setattr(scoring, "get_spark", lambda: object())
    monkeypatch.setattr(scoring, "rule_scores", lambda s, rows: {r["id"]: 10.0 * r["id"] for r in rows})
    monkeypatch.setattr(scoring, "TOP_N_SEGMENTS", 2)
    return updates


def test_scoring_with_provider_blends_scores(monkeypatch):
    updates = _patch_scoring(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(scoring.llm, "score_segment", lambda text: ClipScore(score=90, title="IA", hook="h", hashtags=["#a"]))
    assert scoring.score_pending() == 1
    final = [p for sql, p in updates if "final_score" in sql and p and len(p) == 6]
    assert {p[2] for p in final} == {"IA"}
    assert sorted(round(p[1], 1) for p in final) == [0.4 * 20 + 54, 0.4 * 30 + 54]


def test_scoring_without_provider_never_calls_ai(monkeypatch):
    updates = _patch_scoring(monkeypatch)
    monkeypatch.setenv("LLM_PROVIDER", "none")

    def boom(text):
        raise AssertionError("no debe llamarse a la IA")

    monkeypatch.setattr(scoring.llm, "score_segment", boom)
    assert scoring.score_pending() == 1
    final = [p for sql, p in updates if "final_score" in sql and p and len(p) == 6]
    assert all(p[0] is None and p[4] == scoring.DEFAULT_HASHTAGS for p in final)
