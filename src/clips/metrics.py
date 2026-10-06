"""Recolección de métricas por clip.

Fuentes (METRICS_SOURCE):
  manual     -> lee data/metrics_input.csv (clip_id,views,likes,shares,avg_watch_time),
                que se llena a mano con los números de TikTok Studio.  [por defecto]
  simulated  -> genera métricas sintéticas y deterministas para demostrar el flujo.
                Se guardan con source='simulated' y NO se usan para aprender pesos
                salvo que INSIGHTS_INCLUDE_SIMULATED=true.
"""
import csv
import os
import random
from pathlib import Path

from clips import db
from clips.config import DATA_DIR

METRICS_FILE = Path(os.getenv("METRICS_FILE", str(DATA_DIR / "metrics_input.csv")))
TRACKED = ("published", "in_inbox", "ready_manual")


def read_manual_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(
                {
                    "clip_id": int(r["clip_id"]),
                    "views": int(r["views"]),
                    "likes": int(r.get("likes") or 0),
                    "shares": int(r.get("shares") or 0),
                    "avg_watch_time": float(r["avg_watch_time"]) if r.get("avg_watch_time") else None,
                }
            )
    return rows


def simulate_metrics(clip_id: int, final_score: float | None, duration_s: float) -> dict:
    """Métricas sintéticas deterministas: el puntaje y la duración influyen un poco, más ruido."""
    rng = random.Random(clip_id)
    quality = (final_score or 50.0) / 100.0
    views = int(500 + 9000 * quality * rng.uniform(0.4, 1.6))
    rate = min(0.25, max(0.01, 0.03 + 0.08 * quality + rng.uniform(-0.02, 0.02)))
    likes = int(views * rate)
    shares = int(likes * rng.uniform(0.05, 0.25))
    watch = round(duration_s * min(0.95, max(0.2, 0.35 + 0.4 * quality + rng.uniform(-0.1, 0.1))), 1)
    return {"clip_id": clip_id, "views": views, "likes": likes, "shares": shares, "avg_watch_time": watch}


def _unchanged(latest: dict | None, m: dict) -> bool:
    return bool(latest) and all(latest[k] == m[k] for k in ("views", "likes", "shares", "avg_watch_time"))


def collect_metrics() -> int:
    source = os.getenv("METRICS_SOURCE", "manual").strip().lower()
    clips = db.query(
        "SELECT c.id, s.final_score, s.end_s - s.start_s AS duration FROM clips c "
        "JOIN segments s ON s.id = c.segment_id WHERE c.status = ANY(%s)",
        (list(TRACKED),),
    )
    known = {c["id"] for c in clips}
    if source == "simulated":
        batch = [simulate_metrics(c["id"], c["final_score"], c["duration"]) for c in clips]
    elif source == "manual":
        batch = [m for m in read_manual_csv(METRICS_FILE) if m["clip_id"] in known]
    else:
        raise ValueError(f"METRICS_SOURCE desconocido: {source!r} (usa manual o simulated)")

    saved = 0
    for m in batch:
        latest = db.query(
            "SELECT views, likes, shares, avg_watch_time FROM clip_metrics "
            "WHERE clip_id = %s AND source = %s ORDER BY captured_at DESC LIMIT 1",
            (m["clip_id"], source),
        )
        if _unchanged(latest[0] if latest else None, m):
            continue  # idempotente: no duplica snapshots idénticos
        db.execute(
            "INSERT INTO clip_metrics (clip_id, views, likes, shares, avg_watch_time, source) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (m["clip_id"], m["views"], m["likes"], m["shares"], m["avg_watch_time"], source),
        )
        saved += 1
    return saved
