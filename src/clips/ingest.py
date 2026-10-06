import subprocess
from pathlib import Path

from clips import db
from clips.config import SOURCES_FILE, VIDEOS_DIR


def read_sources(path: Path = SOURCES_FILE) -> list[str]:
    lines = [l.strip() for l in path.read_text().splitlines()]
    return [l for l in lines if l and not l.startswith("#")]


LOCAL_PREFIX = "file:"


def resolve_local(entry: str) -> Path:
    """'file:mi_video.mp4' -> VIDEOS_DIR/mi_video.mp4; una ruta absoluta se usa tal cual."""
    raw = entry[len(LOCAL_PREFIX):].strip()
    if not raw:
        raise ValueError(f"Entrada local vacía en sources.txt: {entry!r}")
    path = Path(raw)
    return path if path.is_absolute() else VIDEOS_DIR / path


def register_local(entry: str) -> tuple[str, str]:
    """Valida un video local y devuelve (título, ruta)."""
    path = resolve_local(entry)
    if not path.is_file():
        raise FileNotFoundError(
            f"No existe el video local {path}. Cópialo a data/videos/ y usa file:<nombre> en sources.txt"
        )
    if not has_audio(str(path)):
        raise RuntimeError(f"El video local no tiene pista de audio: {path}")
    return path.stem, str(path)


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
        title, path = register_local(url) if url.startswith(LOCAL_PREFIX) else download(url)
        db.execute(
            "INSERT INTO videos (source_url, title, local_path) VALUES (%s, %s, %s) "
            "ON CONFLICT (source_url) DO NOTHING",
            (url, title, path),
        )
    return len(new)
