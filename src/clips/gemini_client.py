import os
import time

from clips import db
from clips.claude_client import SYSTEM, ClipScore, parse_score  # mismo prompt y esquema para ambos proveedores

DEFAULT_MODEL = "gemini-3.8-flash"  # verifica el nombre vigente en AI Studio y cámbialo con GEMINI_MODEL
MAX_BACKOFF_S = 60
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


def _max_tries() -> int:
    return max(1, int(os.getenv("GEMINI_MAX_TRIES", "6")))


def _models(model: str | None) -> list[str]:
    """Modelo principal y, si está definido, uno de respaldo para cuando el principal está saturado."""
    primary = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    fallback = os.getenv("GEMINI_FALLBACK_MODEL", "").strip()
    return [primary] + ([fallback] if fallback and fallback != primary else [])


def _generate(client, model: str, text: str, config, tries: int):
    for attempt in range(tries):
        _throttle()
        try:
            return client.models.generate_content(model=model, contents=f"Segmento:\n{text}", config=config)
        except Exception as exc:
            if attempt == tries - 1 or not is_retryable(exc):
                raise
            time.sleep(min(5 * 2**attempt, MAX_BACKOFF_S))  # 5, 10, 20, 40, 60 s
    raise AssertionError("inalcanzable")


def score_segment(text: str, model: str | None = None) -> ClipScore:
    from google.genai import types

    client = _client()
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM,
        response_mime_type="application/json",
        temperature=0.3,
        max_output_tokens=2048,  # margen: en modelos con "thinking" esos tokens cuentan aquí
    )
    candidates = _models(model)
    for i, name in enumerate(candidates):
        try:
            resp = _generate(client, name, text, config, _max_tries() if i == 0 else 2)
            model = name
            break
        except Exception as exc:
            if i == len(candidates) - 1 or not is_retryable(exc):
                raise
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
