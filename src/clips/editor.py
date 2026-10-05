import subprocess
from pathlib import Path

from clips import db
from clips.config import CLIPS_DIR


def build_ffmpeg_cmd(src: str, start: float, end: float, out: str) -> list[str]:
    """Recorta y convierte a vertical 9:16 (1080x1920)."""
    return [
        "ffmpeg", "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", src,
        "-vf", "crop=ih*9/16:ih,scale=1080:1920",
        "-c:v", "libx264", "-c:a", "aac", out,
    ]


def cut_pending() -> int:
    rows = db.query(
        "SELECT s.id, s.start_s, s.end_s, v.local_path FROM segments s "
        "JOIN videos v ON v.id = s.video_id "
        "LEFT JOIN clips c ON c.segment_id = s.id WHERE s.selected AND c.id IS NULL"
    )
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    for r in rows:
        out = str(Path(CLIPS_DIR) / f"clip_{r['id']}.mp4")
        subprocess.run(build_ffmpeg_cmd(r["local_path"], r["start_s"], r["end_s"], out), check=True)
        db.execute("INSERT INTO clips (segment_id, file_path) VALUES (%s, %s)", (r["id"], out))
    return len(rows)
