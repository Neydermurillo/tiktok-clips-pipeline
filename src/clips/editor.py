import subprocess
from pathlib import Path

from clips import db
from clips.config import CLIPS_DIR
from clips.subtitles import make_srt

SUB_STYLE = "Alignment=2,FontSize=8,Outline=1,Bold=1,MarginV=60"


def _escape_filter_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def build_ffmpeg_cmd(src: str, start: float, end: float, out: str, srt: str | None = None) -> list[str]:
    """Recorta, convierte a vertical 9:16 (1080x1920) y, si hay SRT, quema los subtítulos."""
    vf = "crop=ih*9/16:ih,scale=1080:1920"
    if srt:
        vf += f",subtitles='{_escape_filter_path(srt)}':force_style='{SUB_STYLE}'"
    return [
        "ffmpeg", "-y", "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", src,
        "-vf", vf, "-c:v", "libx264", "-c:a", "aac", out,
    ]


def cut_pending() -> int:
    rows = db.query(
        "SELECT s.id, s.video_id, s.start_s, s.end_s, v.local_path FROM segments s "
        "JOIN videos v ON v.id = s.video_id "
        "LEFT JOIN clips c ON c.segment_id = s.id WHERE s.selected AND c.id IS NULL"
    )
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)
    for r in rows:
        out = str(Path(CLIPS_DIR) / f"clip_{r['id']}.mp4")
        lines = db.query(
            "SELECT start_s, end_s, text FROM transcript_lines WHERE video_id = %s ORDER BY start_s",
            (r["video_id"],),
        )
        srt_text = make_srt(lines, r["start_s"], r["end_s"])
        srt_path = None
        if srt_text:
            srt_path = str(Path(CLIPS_DIR) / f"clip_{r['id']}.srt")
            Path(srt_path).write_text(srt_text, encoding="utf-8")
        subprocess.run(
            build_ffmpeg_cmd(r["local_path"], r["start_s"], r["end_s"], out, srt_path), check=True
        )
        db.execute("INSERT INTO clips (segment_id, file_path) VALUES (%s, %s)", (r["id"], out))
    return len(rows)
