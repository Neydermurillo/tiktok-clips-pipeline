"""Capa de proveedores de IA: elige Gemini, Claude o ninguno según LLM_PROVIDER."""
import os

VALID = ("none", "gemini", "claude")


def provider() -> str:
    """LLM_PROVIDER = none | gemini | claude. Si no está definido, se respeta USE_CLAUDE (antiguo)."""
    p = os.getenv("LLM_PROVIDER", "").strip().lower()
    if not p:
        legacy = os.getenv("USE_CLAUDE", "false").strip().lower()
        return "claude" if legacy in ("true", "1", "yes", "si", "sí") else "none"
    if p not in VALID:
        raise ValueError(f"LLM_PROVIDER inválido: {p!r}. Usa none, gemini o claude.")
    return p


def score_segment(text: str):
    """Devuelve un ClipScore (score, title, hook, hashtags) con el proveedor activo."""
    p = provider()
    if p == "gemini":
        from clips.gemini_client import score_segment as fn
    elif p == "claude":
        from clips.claude_client import score_segment as fn
    else:
        raise RuntimeError("LLM_PROVIDER=none: no hay proveedor de IA configurado")
    return fn(text)
