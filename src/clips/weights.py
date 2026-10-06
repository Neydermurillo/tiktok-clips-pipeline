"""Pesos de la mezcla regla/IA. Por defecto 0.4/0.6; la Fase 3 los ajusta con datos reales."""
import os

from clips import db

DEFAULT_WEIGHTS = (0.4, 0.6)  # (w_rule, w_ai)


def stored_weights() -> tuple[float, float]:
    """Última fila de scoring_weights; si no hay (o la tabla no existe), los valores por defecto."""
    try:
        rows = db.query("SELECT w_rule, w_ai FROM scoring_weights ORDER BY id DESC LIMIT 1")
        row = rows[0] if rows else None
        if row and "w_rule" in row and "w_ai" in row:
            return float(row["w_rule"]), float(row["w_ai"])
    except Exception:
        pass
    return DEFAULT_WEIGHTS


def ai_weight_override() -> float | None:
    """AI_WEIGHT (0 a 1) fija a mano la importancia de la IA y tiene prioridad sobre lo aprendido."""
    raw = os.getenv("AI_WEIGHT", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"AI_WEIGHT debe ser un número entre 0 y 1, no {raw!r}") from None
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"AI_WEIGHT debe estar entre 0 y 1, no {value}")
    return value


def current_weights() -> tuple[float, float]:
    """(w_regla, w_ia) que usa el scoring: AI_WEIGHT si está definido; si no, lo aprendido o 0.4/0.6."""
    override = ai_weight_override()
    if override is not None:
        return round(1 - override, 4), override
    return stored_weights()
