import re

MAX_LEN = 2200  # límite de título en Direct Post según la documentación de TikTok


def build_caption(title: str, hashtags: list[str] | None, max_len: int = MAX_LEN) -> str:
    seen, tags = set(), []
    for h in hashtags or []:
        tag = "#" + re.sub(r"[^\wáéíóúñü]", "", h.lstrip("#"), flags=re.I)
        if len(tag) > 1 and tag.lower() not in seen:
            seen.add(tag.lower())
            tags.append(tag)
    caption = " ".join([(title or "").strip(), *tags]).strip()
    return caption[:max_len]
