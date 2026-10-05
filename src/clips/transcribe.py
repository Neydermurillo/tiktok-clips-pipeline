from clips import db
from clips.config import WHISPER_MODEL
from clips.segmentation import build_candidates


def transcribe_file(path: str) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel(WHISPER_MODEL, compute_type="int8")
    segments, _ = model.transcribe(path)
    return [{"start": s.start, "end": s.end, "text": s.text} for s in segments]


def transcribe_pending() -> int:
    videos = db.query("SELECT id, local_path FROM videos WHERE status = 'downloaded'")
    for v in videos:
        lines = transcribe_file(v["local_path"])
        for ln in lines:
            db.execute(
                "INSERT INTO transcript_lines (video_id, start_s, end_s, text) VALUES (%s,%s,%s,%s)",
                (v["id"], ln["start"], ln["end"], ln["text"].strip()),
            )
        candidates = build_candidates(lines)
        for c in candidates:
            db.execute(
                "INSERT INTO segments (video_id, start_s, end_s, text) VALUES (%s, %s, %s, %s)",
                (v["id"], c["start_s"], c["end_s"], c["text"]),
            )
        db.execute("UPDATE videos SET status = 'transcribed' WHERE id = %s", (v["id"],))
    return len(videos)
