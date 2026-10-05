from clips import db
from clips.claude_client import score_segment
from clips.config import KEEP_K_CLIPS, TOP_N_SEGMENTS
from clips.scoring_spark import get_spark, rule_scores


def score_pending() -> int:
    videos = db.query("SELECT id FROM videos WHERE status = 'transcribed'")
    spark = get_spark() if videos else None
    for v in videos:
        segs = db.query(
            "SELECT id, text, end_s - start_s AS duration FROM segments WHERE video_id = %s",
            (v["id"],),
        )
        scores = rule_scores(spark, [dict(s) for s in segs])
        for sid, sc in scores.items():
            db.execute("UPDATE segments SET rule_score = %s WHERE id = %s", (sc, sid))

        # Claude solo evalúa los mejores candidatos (ahorra costo)
        top = sorted(segs, key=lambda s: scores[s["id"]], reverse=True)[:TOP_N_SEGMENTS]
        for s in top:
            res = score_segment(s["text"])
            final = 0.4 * scores[s["id"]] + 0.6 * res.score
            db.execute(
                "UPDATE segments SET claude_score=%s, final_score=%s, title=%s, hook=%s, hashtags=%s "
                "WHERE id=%s",
                (res.score, final, res.title, res.hook, res.hashtags, s["id"]),
            )
        db.execute(
            "UPDATE segments SET selected = TRUE WHERE id IN ("
            "SELECT id FROM segments WHERE video_id = %s AND final_score IS NOT NULL "
            "ORDER BY final_score DESC LIMIT %s)",
            (v["id"], KEEP_K_CLIPS),
        )
        db.execute("UPDATE videos SET status = 'scored' WHERE id = %s", (v["id"],))
    return len(videos)
