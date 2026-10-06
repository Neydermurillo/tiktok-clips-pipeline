import os
from pathlib import Path

DB_DSN = os.getenv("CLIPS_DB_DSN", "postgresql://airflow:airflow@localhost:5432/clips")
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
VIDEOS_DIR = DATA_DIR / "videos"
CLIPS_DIR = DATA_DIR / "clips"
SOURCES_FILE = Path(os.getenv("SOURCES_FILE", "config/sources.txt"))

MODEL_FAST = os.getenv("CLAUDE_MODEL_FAST", "claude-haiku-4-5-20251001")
MODEL_SMART = os.getenv("CLAUDE_MODEL_SMART", "claude-sonnet-5-5")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

MIN_CLIP_S = 20
MAX_CLIP_S = 60
# Si al final del video queda una cola menor a MIN_CLIP_S, se une a la última ventana mientras el
# clip resultante no pase de este tope (segundos). 0 = descartar siempre la cola.
TAIL_MERGE_MAX_S = float(os.getenv("TAIL_MERGE_MAX_S", "90"))
TOP_N_SEGMENTS = int(os.getenv("TOP_N_SEGMENTS", "10"))
KEEP_K_CLIPS = int(os.getenv("KEEP_K_CLIPS", "3"))

KEYWORDS = [
    "secreto", "error", "nunca", "siempre", "increíble", "truco", "clave", "por qué",
    "secret", "mistake", "never", "always", "amazing", "trick", "key", "why", "how to",
]
