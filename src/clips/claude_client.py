import json
import re

from pydantic import BaseModel, Field

from clips import db
from clips.config import MODEL_FAST

SYSTEM = (
    "Eres editor de clips cortos para TikTok. Evalúa el potencial viral del segmento de "
    "transcripción. Responde SOLO con JSON válido, sin texto adicional ni markdown: "
    '{"score": 0-100, "title": str, "hook": str, "hashtags": [str]}'
)


class ClipScore(BaseModel):
    score: int = Field(ge=0, le=100)
    title: str
    hook: str
    hashtags: list[str]


def parse_score(raw: str) -> ClipScore:
    """Tolera bloques ```json y texto alrededor del JSON."""
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("La respuesta no contiene JSON")
    return ClipScore(**json.loads(raw[start : end + 1]))


def score_segment(text: str, model: str = MODEL_FAST) -> ClipScore:
    import anthropic

    client = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY del entorno
    msg = client.messages.create(
        model=model,
        max_tokens=400,
        system=SYSTEM,
        messages=[{"role": "user", "content": f"Segmento:\n{text}"}],
    )
    db.execute(
        "INSERT INTO llm_calls (task, model, input_tokens, output_tokens) VALUES (%s,%s,%s,%s)",
        ("score_segment", model, msg.usage.input_tokens, msg.usage.output_tokens),
    )
    return parse_score(msg.content[0].text)
