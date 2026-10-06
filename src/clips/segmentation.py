from clips.config import MAX_CLIP_S, MIN_CLIP_S, TAIL_MERGE_MAX_S


def build_candidates(
    segments: list[dict],
    min_s: float = MIN_CLIP_S,
    max_s: float = MAX_CLIP_S,
    tail_max_s: float = TAIL_MERGE_MAX_S,
) -> list[dict]:
    """Agrupa segmentos de Whisper ({start, end, text}) en ventanas candidatas de min_s..max_s.

    La cola final (menor a min_s) se une a la última ventana si el resultado no pasa de tail_max_s;
    así no se pierde el cierre del video. Con tail_max_s=0 la cola se descarta.
    """
    out, buf = [], []
    for seg in segments:
        buf.append(seg)
        dur = buf[-1]["end"] - buf[0]["start"]
        ends_sentence = seg["text"].strip().endswith((".", "?", "!"))
        if dur >= max_s or (dur >= min_s and ends_sentence):
            out.append(_flush(buf))
            buf = []
    if buf:
        if buf[-1]["end"] - buf[0]["start"] >= min_s:
            out.append(_flush(buf))
        elif out and buf[-1]["end"] - out[-1]["start_s"] <= tail_max_s:
            tail = _flush(buf)
            out[-1]["end_s"] = tail["end_s"]
            out[-1]["text"] += " " + tail["text"]
    return out


def _flush(buf: list[dict]) -> dict:
    return {
        "start_s": buf[0]["start"],
        "end_s": buf[-1]["end"],
        "text": " ".join(s["text"].strip() for s in buf),
    }
