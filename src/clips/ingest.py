from pathlib import Path

from clips import db
from clips.config import SOURCES_FILE, VIDEOS_DIR


def read_sources(path: Path = SOURCES_FILE) -> list[str]:
    lines = [l.strip() for l in path.read_text().splitlines()]
    return [l for l in lines if l and not l.startswith("#")]


def download(url: str) -> tuple[str, str]:
    from yt_dlp import YoutubeDL

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    opts = {"outtmpl": str(VIDEOS_DIR / "%(id)s.%(ext)s"), "format": "mp4/best", "quiet": True}
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info.get("title", ""), ydl.prepare_filename(info)


def ingest_new_videos() -> int:
    """Descarga las URLs que aún no están en la base de datos. Idempotente."""
    known = {r["source_url"] for r in db.query("SELECT source_url FROM videos")}
    new = [u for u in read_sources() if u not in known]
    for url in new:
        title, path = download(url)
        db.execute(
            "INSERT INTO videos (source_url, title, local_path) VALUES (%s, %s, %s) "
            "ON CONFLICT (source_url) DO NOTHING",
            (url, title, path),
        )
    return len(new)
