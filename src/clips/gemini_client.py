import os
import time

from clips import db
from clips.claude_client import SYSTEM, ClipScore, parse_score  # mismo prompt y esquema para ambos proveedores

DEFAULT_MODEL = "gemini-2.5-flash"  # verifica el nombre vigente en AI Studio y cámbialo con GEMINI_MODEL
MAX_TRIES = 4
RETRYABLE = (429, 500, 503)
_last_call = 0.0


def _client():
    from google import genai

    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Falta GEMINI_API_KEY en el archivo .env")
    return genai.Client(api_key=key)


def is_retryable(exc: Exception) -> bool:
    return getattr(exc, "code", None) in RETRYABLE


def _throttle() -> None:
    """Espacia las llamadas para respetar el límite de peticiones por minuto del plan gratuito."""
    global _last_call
    wait = float(os.getenv("GEMINI_MIN_INTERVAL_S", "4")) - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def score_segment(text: str, model: str | None = None) -> ClipScore:
    from google.genai import types

    model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    client = _client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        response_mime_type="application/json",
        temperature=0.3,
        max_output_tokens=2048,  # margen: en modelos con "thinking" esos tokens cuentan aquí
    )
    for attempt in range(MAX_TRIES):
        _throttle()
        try:
            resp = client.models.generate_content(model=model, contents=f"Segmento:\n{text}", config=config)
            break
        except Exception as exc:
            if attempt == MAX_TRIES - 1 or not is_retryable(exc):
                raise
            time.sleep(5 * 2**attempt)  # 5 s, 10 s, 20 s
    usage = getattr(resp, "usage_metadata", None)
    db.execute(
        "INSERT INTO llm_calls (task, model, input_tokens, output_tokens) VALUES (%s,%s,%s,%s)",
        (
            "score_segment",
            f"gemini:{model}",
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "candidates_token_count", None),
        ),
    )
    if not resp.text:
        raise ValueError("Gemini devolvió una respuesta vacía (posible bloqueo de contenido)")
    return parse_score(resp.text)
