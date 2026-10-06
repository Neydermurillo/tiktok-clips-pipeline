"""Bucle de retroalimentación: ¿qué señal predice mejor el engagement, la regla o la IA?

PySpark calcula la correlación de cada puntaje con la tasa de engagement de los clips
publicados y, con suficientes muestras, ajusta los pesos de la mezcla final.
"""
import logging
import math
import os

from clips import db
from clips.scoring_spark import get_spark
from clips.weights import DEFAULT_WEIGHTS, stored_weights

log = logging.getLogger(__name__)
MIN_SAMPLES = int(os.getenv("INSIGHTS_MIN_SAMPLES", "10"))
W_MIN, W_MAX = 0.2, 0.8
SMOOTHING = 0.5  # 0 = ignora los datos, 1 = usa solo lo aprendido


def engagement_rate(views: int, likes: int, shares: int) -> float:
    """(likes + 2*shares) / views. 0 si no hay vistas."""
    return (likes + 2 * shares) / views if views else 0.0


def compute_weights(corr_rule, corr_ai, n_samples, min_samples=MIN_SAMPLES, current=DEFAULT_WEIGHTS):
    """Devuelve (w_rule, w_ai). Mantiene los pesos actuales si hay pocos datos o ninguna señal positiva."""
    def ok(x):
        return x is not None and not math.isnan(x)

    if n_samples < min_samples or not (ok(corr_rule) and ok(corr_ai)):
        return current
    a, b = max(corr_rule, 0.0), max(corr_ai, 0.0)
    if a + b == 0:
        return current
    learned_rule = a / (a + b)
    w_rule = (1 - SMOOTHING) * current[0] + SMOOTHING * learned_rule
    w_rule = min(W_MAX, max(W_MIN, w_rule))
    return round(w_rule, 4), round(1 - w_rule, 4)


def spark_correlations(spark, rows: list[dict]) -> tuple[float | None, float | None]:
    """rows: [{rule_score, ai_score, engagement}] -> (corr_rule, corr_ai) calculadas con PySpark."""
    if len(rows) < 2:
        return None, None
    df = spark.createDataFrame(rows)
    return df.stat.corr("rule_score", "engagement"), df.stat.corr("ai_score", "engagement")


def update_weights() -> dict:
    include_sim = os.getenv("INSIGHTS_INCLUDE_SIMULATED", "false").strip().lower() in ("true", "1", "yes")
    sources = ["manual", "tiktok"] + (["simulated"] if include_sim else [])
    rows = db.query(
        "SELECT DISTINCT ON (m.clip_id) m.views, m.likes, m.shares, s.rule_score, s.claude_score "
        "FROM clip_metrics m JOIN clips c ON c.id = m.clip_id JOIN segments s ON s.id = c.segment_id "
        "WHERE m.source = ANY(%s) AND s.rule_score IS NOT NULL AND s.claude_score IS NOT NULL "
        "ORDER BY m.clip_id, m.captured_at DESC",
        (sources,),
    )
    data = [
        {
            "rule_score": float(r["rule_score"]),
            "ai_score": float(r["claude_score"]),
            "engagement": engagement_rate(r["views"] or 0, r["likes"] or 0, r["shares"] or 0),
        }
        for r in rows
    ]
    n = len(data)
    if n < 2:
        log.info("Muestras insuficientes (%s) para calcular correlaciones", n)
        return {"n": n, "updated": False}
    corr_rule, corr_ai = spark_correlations(get_spark(), data)
    current = stored_weights()  # lo aprendido, no el AI_WEIGHT manual
    new = compute_weights(corr_rule, corr_ai, n, current=current)
    updated = new != current
    log.info("n=%s corr_rule=%s corr_ai=%s pesos %s -> %s", n, corr_rule, corr_ai, current, new)
    if updated:
        db.execute(
            "INSERT INTO scoring_weights (w_rule, w_ai, n_samples, corr_rule, corr_ai) "
            "VALUES (%s, %s, %s, %s, %s)",
            (new[0], new[1], n, corr_rule, corr_ai),
        )
    return {"n": n, "updated": updated, "w_rule": new[0], "w_ai": new[1]}
