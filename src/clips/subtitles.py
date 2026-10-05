import textwrap


def fmt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_srt(lines: list[dict], start: float, end: float, width: int = 28) -> str:
    """lines: [{start_s, end_s, text}] del video completo -> SRT con tiempos relativos al clip."""
    blocks, idx = [], 1
    for ln in lines:
        if ln["end_s"] <= start or ln["start_s"] >= end:
            continue
        text = "\n".join(textwrap.wrap(ln["text"].strip(), width))
        if not text:
            continue
        s = max(ln["start_s"], start) - start
        e = min(ln["end_s"], end) - start
        blocks.append(f"{idx}\n{fmt_ts(s)} --> {fmt_ts(e)}\n{text}\n")
        idx += 1
    return "\n".join(blocks)
