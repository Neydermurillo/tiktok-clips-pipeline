import csv
import os
import time
from pathlib import Path

from clips import db, tiktok
from clips.caption import build_caption
from clips.config import CLIPS_DIR

MODE = os.getenv("TIKTOK_MODE", "manual")  # manual | draft | direct
PRIVACY = os.getenv("TIKTOK_PRIVACY", "SELF_ONLY")
PER_RUN = int(os.getenv("PUBLISH_PER_RUN", "3"))
POLL_TRIES, POLL_SLEEP = 6, 10


def status_to_clip_status(tiktok_status: str) -> str:
    return {
        "PUBLISH_COMPLETE": "published",
        "SEND_TO_USER_INBOX": "in_inbox",
        "FAILED": "failed",
    }.get(tiktok_status, "processing")


def _write_manual_queue(items: list[dict]) -> None:
    path = Path(CLIPS_DIR) / "publish_queue.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["clip_id", "file_path", "caption"])
        if new:
            w.writeheader()
        w.writerows(items)


def publish_pending() -> int:
    rows = db.query(
        "SELECT c.id, c.file_path, s.title, s.hashtags FROM clips c "
        "JOIN segments s ON s.id = c.segment_id WHERE c.status = 'rendered' "
        "ORDER BY s.final_score DESC LIMIT %s",
        (PER_RUN,),
    )
    manual = []
    for r in rows:
        caption = build_caption(r["title"], r["hashtags"])
        if MODE == "manual":
            manual.append({"clip_id": r["id"], "file_path": r["file_path"], "caption": caption})
            db.execute("UPDATE clips SET status='ready_manual', caption=%s WHERE id=%s", (caption, r["id"]))
            continue
        try:
            token = os.environ["TIKTOK_ACCESS_TOKEN"]
            size = os.path.getsize(r["file_path"])
            publish_id, upload_url = tiktok.init_upload(token, MODE, size, caption, PRIVACY)
            db.execute(
                "UPDATE clips SET publish_id=%s, caption=%s, status='processing' WHERE id=%s",
                (publish_id, caption, r["id"]),
            )
            tiktok.upload_file(upload_url, r["file_path"])
            status = "UNKNOWN"
            for _ in range(POLL_TRIES):
                status = tiktok.fetch_status(token, publish_id)
                if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX", "FAILED"):
                    break
                time.sleep(POLL_SLEEP)
            new_status = status_to_clip_status(status)
            db.execute(
                "UPDATE clips SET status=%s, published_at = CASE WHEN %s='published' THEN now() END "
                "WHERE id=%s",
                (new_status, new_status, r["id"]),
            )
        except Exception as exc:  # un clip fallido no debe tumbar el lote
            db.execute("UPDATE clips SET status='failed', error=%s WHERE id=%s", (str(exc)[:500], r["id"]))
    if manual:
        _write_manual_queue(manual)
    return len(rows)
