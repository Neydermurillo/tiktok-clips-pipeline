from clips.config import MAX_CLIP_S, MIN_CLIP_S


def build_candidates(
    segments: list[dict], min_s: float = MIN_CLIP_S, max_s: float = MAX_CLIP_S
) -> list[dict]:
    """Agrupa segmentos de Whisper ({start, end, text}) en ventanas candidatas de min_s..max_s."""
    out, buf = [], []
    for seg in segments:
        buf.append(seg)
        dur = buf[-1]["end"] - buf[0]["start"]
        ends_sentence = seg["text"].strip().endswith((".", "?", "!"))
        if dur >= max_s or (dur >= min_s and ends_sentence):
            out.append(_flush(buf))
            buf = []
    if buf and buf[-1]["end"] - buf[0]["start"] >= min_s:
        out.append(_flush(buf))
    return out


def _flush(buf: list[dict]) -> dict:
    return {
        "start_s": buf[0]["start"],
        "end_s": buf[-1]["end"],
        "text": " ".join(s["text"].strip() for s in buf),
    }
