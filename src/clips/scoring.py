import logging
import re

from clips import db, llm, weights
from clips.config import KEEP_K_CLIPS, TOP_N_SEGMENTS
from clips.scoring_spark import get_spark, rule_scores

log = logging.getLogger(__name__)
DEFAULT_HASHTAGS = ["#fyp", "#parati", "#viral"]


def local_metadata(text: str) -> tuple[str, str, list[str]]:
    """Título, hook y hashtags básicos sin IA: usa la primera frase del segmento."""
    clean = " ".join(text.split())
    first = re.split(r"(?<=[.!?])\s", clean, maxsplit=1)[0]
    title = (first[:70].rstrip() + "…") if len(first) > 70 else first
    return title, first[:140], DEFAULT_HASHTAGS


def score_pending() -> int:
    provider = llm.provider()
    log.info("Proveedor de IA para el scoring: %s", provider)
    w_rule, w_ai = weights.current_weights()
    log.info("Pesos de la mezcla: regla=%s, IA=%s", w_rule, w_ai)
    videos = db.query("SELECT id FROM videos WHERE status = 'transcribed'")
    spark = get_spark() if videos else None
    for v in videos:
        segs = db.query(
            "SELECT id, text, end_s - start_s AS duration, final_score FROM segments WHERE video_id = %s",
            (v["id"],),
        )
        # a Spark solo las columnas necesarias: un final_score todo NULL rompe la inferencia de tipos
        scores = rule_scores(spark, [{"id": s["id"], "text": s["text"], "duration": s["duration"]} for s in segs])
        for sid, sc in scores.items():
            db.execute("UPDATE segments SET rule_score = %s WHERE id = %s", (sc, sid))

        # Solo los mejores candidatos reciben puntaje final (y llamada a la IA si hay proveedor)
        top = sorted(segs, key=lambda s: scores[s["id"]], reverse=True)[:TOP_N_SEGMENTS]
        for s in top:
            if s.get("final_score") is not None:
                continue  # ya puntuado en un intento anterior: no gastes cuota de la IA otra vez
            if provider != "none":
                res = llm.score_segment(s["text"])
                llm_score, final = res.score, w_rule * scores[s["id"]] + w_ai * res.score
                title, hook, hashtags = res.title, res.hook, res.hashtags
            else:
                llm_score, final = None, scores[s["id"]]
                title, hook, hashtags = local_metadata(s["text"])
            # la columna se llama claude_score por historia; guarda el puntaje del proveedor activo
            db.execute(
                "UPDATE segments SET claude_score=%s, final_score=%s, title=%s, hook=%s, hashtags=%s "
                "WHERE id=%s",
                (llm_score, final, title, hook, hashtags, s["id"]),
            )
        db.execute(
            "UPDATE segments SET selected = TRUE WHERE id IN ("
            "SELECT id FROM segments WHERE video_id = %s AND final_score IS NOT NULL "
            "ORDER BY final_score DESC LIMIT %s)",
            (v["id"], KEEP_K_CLIPS),
        )
        db.execute("UPDATE videos SET status = 'scored' WHERE id = %s", (v["id"],))
    return len(videos)
