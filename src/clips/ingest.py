import subprocess
from pathlib import Path

from clips import db
from clips.config import SOURCES_FILE, VIDEOS_DIR


def read_sources(path: Path = SOURCES_FILE) -> list[str]:
    lines = [l.strip() for l in path.read_text().splitlines()]
    return [l for l in lines if l and not l.startswith("#")]


def has_audio(path: str) -> bool:
    """True si el archivo tiene al menos una pista de audio."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    return out.returncode == 0 and bool(out.stdout.strip())


def download(url: str) -> tuple[str, str]:
    from yt_dlp import YoutubeDL

    VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(VIDEOS_DIR / "%(id)s.%(ext)s"),
        # video + audio por separado, unidos con FFmpeg: evita mp4 sin sonido
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
        "merge_output_format": "mp4",
        "quiet": True,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloads = info.get("requested_downloads") or [{}]
        path = downloads[0].get("filepath") or ydl.prepare_filename(info)
    if not has_audio(path):
        raise RuntimeError(f"El video descargado no tiene pista de audio: {path}")
    return info.get("title", ""), path


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