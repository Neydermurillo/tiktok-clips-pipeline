import pytest

from clips import insights, metrics, scoring, weights
from clips.claude_client import ClipScore


# ---------- métricas ----------
def test_read_manual_csv(tmp_path):
    f = tmp_path / "m.csv"
    f.write_text("clip_id,views,likes,shares,avg_watch_time\n1,1000,50,5,12.5\n2,200,,,\n", encoding="utf-8")
    rows = metrics.read_manual_csv(f)
    assert rows[0] == {"clip_id": 1, "views": 1000, "likes": 50, "shares": 5, "avg_watch_time": 12.5}
    assert rows[1]["likes"] == 0 and rows[1]["avg_watch_time"] is None


def test_read_manual_csv_missing_file(tmp_path):
    assert metrics.read_manual_csv(tmp_path / "no.csv") == []


def test_simulated_is_deterministic_and_sane():
    a = metrics.simulate_metrics(7, 80.0, 30.0)
    assert a == metrics.simulate_metrics(7, 80.0, 30.0)
    assert a["views"] > 0 and a["likes"] <= a["views"] and 0 < a["avg_watch_time"] <= 30.0


def _patch_collect(monkeypatch, latest=None):
    inserted = []

    def query(sql, params=None):
        if "FROM clips" in sql:
            return [{"id": 1, "final_score": 70.0, "duration": 30.0}]
        return latest or []

    monkeypatch.setattr(metrics.db, "query", query)
    monkeypatch.setattr(metrics.db, "execute", lambda sql, params=None: inserted.append(params))
    return inserted


def test_collect_manual_inserts_only_known_clips(monkeypatch, tmp_path):
    f = tmp_path / "m.csv"
    f.write_text("clip_id,views,likes,shares,avg_watch_time\n1,100,10,1,9\n99,5,0,0,1\n", encoding="utf-8")
    monkeypatch.setattr(metrics, "METRICS_FILE", f)
    monkeypatch.setenv("METRICS_SOURCE", "manual")
    inserted = _patch_collect(monkeypatch)
    assert metrics.collect_metrics() == 1
    assert inserted == [(1, 100, 10, 1, 9.0, "manual")]


def test_collect_is_idempotent(monkeypatch, tmp_path):
    f = tmp_path / "m.csv"
    f.write_text("clip_id,views,likes,shares,avg_watch_time\n1,100,10,1,9\n", encoding="utf-8")
    monkeypatch.setattr(metrics, "METRICS_FILE", f)
    monkeypatch.setenv("METRICS_SOURCE", "manual")
    same = [{"views": 100, "likes": 10, "shares": 1, "avg_watch_time": 9.0}]
    inserted = _patch_collect(monkeypatch, latest=same)
    assert metrics.collect_metrics() == 0 and inserted == []


def test_collect_simulated_marks_source(monkeypatch):
    monkeypatch.setenv("METRICS_SOURCE", "simulated")
    inserted = _patch_collect(monkeypatch)
    assert metrics.collect_metrics() == 1
    assert inserted[0][-1] == "simulated"


def test_collect_unknown_source(monkeypatch):
    monkeypatch.setenv("METRICS_SOURCE", "otra")
    _patch_collect(monkeypatch)
    with pytest.raises(ValueError):
        metrics.collect_metrics()


# ---------- pesos ----------
def test_engagement_rate():
    assert insights.engagement_rate(1000, 50, 10) == pytest.approx(0.07)
    assert insights.engagement_rate(0, 5, 5) == 0.0


def test_weights_unchanged_with_few_samples():
    assert insights.compute_weights(0.9, 0.1, 3, min_samples=10) == (0.4, 0.6)


def test_weights_unchanged_with_nan_or_no_signal():
    assert insights.compute_weights(float("nan"), 0.5, 50) == (0.4, 0.6)
    assert insights.compute_weights(-0.3, -0.1, 50) == (0.4, 0.6)


def test_weights_shift_toward_better_signal_and_sum_to_one():
    w_rule, w_ai = insights.compute_weights(0.8, 0.2, 50)
    assert w_rule > 0.4 and w_rule + w_ai == pytest.approx(1.0)
    w_rule, w_ai = insights.compute_weights(0.1, 0.9, 50)
    assert w_ai > 0.6


def test_weights_are_clamped():
    w_rule, _ = insights.compute_weights(1.0, 0.0, 50, current=(0.8, 0.2))
    assert w_rule <= insights.W_MAX
    w_rule, _ = insights.compute_weights(0.0, 1.0, 50, current=(0.2, 0.8))
    assert w_rule >= insights.W_MIN


def test_spark_correlations():
    from clips.scoring_spark import get_spark

    rows = [{"rule_score": float(i), "ai_score": float(10 - i), "engagement": i / 10} for i in range(10)]
    c_rule, c_ai = insights.spark_correlations(get_spark(), rows)
    assert c_rule == pytest.approx(1.0) and c_ai == pytest.approx(-1.0)


def test_spark_correlations_needs_two_rows():
    assert insights.spark_correlations(object(), [{"rule_score": 1.0}]) == (None, None)


def test_current_weights_defaults_when_missing_or_malformed(monkeypatch):
    monkeypatch.delenv("AI_WEIGHT", raising=False)
    monkeypatch.setattr(weights.db, "query", lambda sql, params=None: [])
    assert weights.stored_weights() == weights.DEFAULT_WEIGHTS
    monkeypatch.setattr(weights.db, "query", lambda sql, params=None: [{"id": 1}])
    assert weights.stored_weights() == weights.DEFAULT_WEIGHTS

    def boom(sql, params=None):
        raise RuntimeError("tabla inexistente")

    monkeypatch.setattr(weights.db, "query", boom)
    assert weights.stored_weights() == weights.DEFAULT_WEIGHTS


def test_current_weights_reads_latest(monkeypatch):
    monkeypatch.setattr(weights.db, "query", lambda sql, params=None: [{"w_rule": 0.55, "w_ai": 0.45}])
    assert weights.stored_weights() == (0.55, 0.45)


def test_scoring_uses_learned_weights(monkeypatch):
    updates = []

    def query(sql, params=None):
        if "FROM videos" in sql:
            return [{"id": 1}]
        return [{"id": 1, "text": "Hola. Mundo.", "duration": 30.0}]

    monkeypatch.setattr(scoring.db, "query", query)
    monkeypatch.setattr(scoring.db, "execute", lambda sql, params=None: updates.append((sql, params)))
    monkeypatch.setattr(scoring, "get_spark", lambda: object())
    monkeypatch.setattr(scoring, "rule_scores", lambda s, rows: {1: 50.0})
    monkeypatch.setattr(scoring.weights, "current_weights", lambda: (0.7, 0.3))
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setattr(scoring.llm, "score_segment", lambda t: ClipScore(score=100, title="T", hook="h", hashtags=["#a"]))
    scoring.score_pending()
    final = [p for sql, p in updates if "final_score" in sql and p and len(p) == 6]
    assert final[0][1] == pytest.approx(0.7 * 50 + 0.3 * 100)
