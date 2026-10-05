"""Cliente mínimo de la Content Posting API de TikTok (subida por archivo en bloques)."""
import os

import requests

API = "https://open.tiktokapis.com"
MB = 1024 * 1024
CHUNK = 32 * MB
MAX_SINGLE = 64 * MB
INIT_PATHS = {
    "draft": "/v2/post/publish/inbox/video/init/",  # scope video.upload
    "direct": "/v2/post/publish/video/init/",       # scope video.publish
}


class TikTokError(RuntimeError):
    pass


def plan_chunks(size: int) -> list[tuple[int, int]]:
    """[(inicio, fin_inclusivo)]. Hasta 64 MB va en un bloque; si no, bloques de 32 MB y el último absorbe el resto."""
    if size <= MAX_SINGLE:
        return [(0, size - 1)]
    n = size // CHUNK
    return [(i * CHUNK, size - 1 if i == n - 1 else (i + 1) * CHUNK - 1) for i in range(n)]


def build_init_payload(mode: str, size: int, caption: str, privacy: str) -> dict:
    ranges = plan_chunks(size)
    source = {
        "source": "FILE_UPLOAD",
        "video_size": size,
        "chunk_size": ranges[0][1] - ranges[0][0] + 1,
        "total_chunk_count": len(ranges),
    }
    if mode == "draft":
        return {"source_info": source}
    return {
        "post_info": {
            "title": caption,
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": source,
    }


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}


def _data(resp: requests.Response) -> dict:
    resp.raise_for_status()
    body = resp.json()
    err = body.get("error", {})
    if err.get("code") not in (None, "ok"):
        raise TikTokError(f"{err.get('code')}: {err.get('message')}")
    return body.get("data", {})


def init_upload(token: str, mode: str, size: int, caption: str, privacy: str) -> tuple[str, str]:
    resp = requests.post(
        API + INIT_PATHS[mode],
        json=build_init_payload(mode, size, caption, privacy),
        headers=_headers(token),
        timeout=30,
    )
    data = _data(resp)
    return data["publish_id"], data["upload_url"]


def upload_file(upload_url: str, file_path: str) -> None:
    size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        for start, end in plan_chunks(size):
            f.seek(start)
            chunk = f.read(end - start + 1)
            resp = requests.put(
                upload_url,
                data=chunk,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {start}-{end}/{size}",
                },
                timeout=300,
            )
            if resp.status_code not in (201, 206):
                raise TikTokError(f"Falló la subida ({resp.status_code}): {resp.text[:200]}")


def fetch_status(token: str, publish_id: str) -> str:
    resp = requests.post(
        API + "/v2/post/publish/status/fetch/",
        json={"publish_id": publish_id},
        headers=_headers(token),
        timeout=30,
    )
    return _data(resp).get("status", "UNKNOWN")
