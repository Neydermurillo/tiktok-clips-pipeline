import shutil

import pytest

from clips.claude_client import parse_score
from clips.editor import build_ffmpeg_cmd
from clips.segmentation import build_candidates


def test_build_candidates_groups_until_sentence_end():
    segs = [
        {"start": 0, "end": 10, "text": "hola"},
        {"start": 10, "end": 25, "text": "esto es una idea."},
        {"start": 25, "end": 40, "text": "otra idea"},
    ]
    out = build_candidates(segs, min_s=20, max_s=60)
    assert out[0]["start_s"] == 0 and out[0]["end_s"] == 25
    assert len(out) == 1  # el resto (15s) es menor que min_s


def test_parse_score_tolerates_markdown_fences():
    raw = '```json\n{"score": 80, "title": "t", "hook": "h", "hashtags": ["#a"]}\n```'
    assert parse_score(raw).score == 80


def test_parse_score_rejects_out_of_range():
    with pytest.raises(Exception):
        parse_score('{"score": 150, "title": "t", "hook": "h", "hashtags": []}')


def test_ffmpeg_cmd_is_vertical():
    cmd = build_ffmpeg_cmd("in.mp4", 1.0, 31.0, "out.mp4")
    assert "crop=ih*9/16:ih,scale=1080:1920" in cmd


@pytest.mark.skipif(shutil.which("java") is None, reason="requiere Java")
def test_rule_scores_runs_on_spark():
    from clips.scoring_spark import get_spark, rule_scores

    rows = [{"id": 1, "text": "¿Sabías este secreto? ¡Increíble!", "duration": 5.0},
            {"id": 2, "text": "hmm", "duration": 30.0}]
    scores = rule_scores(get_spark(), rows)
    assert scores[1] > scores[2]


# ---------- Fase 2 ----------
from clips.caption import build_caption
from clips.publisher import status_to_clip_status
from clips.subtitles import fmt_ts, make_srt
from clips import tiktok


def test_fmt_ts():
    assert fmt_ts(3661.5) == "01:01:01,500"


def test_make_srt_relative_times_and_clipping():
    lines = [
        {"start_s": 0, "end_s": 8, "text": "fuera del clip"},
        {"start_s": 8, "end_s": 14, "text": "hola mundo"},
        {"start_s": 14, "end_s": 40, "text": "otra frase"},
    ]
    srt = make_srt(lines, start=10, end=20)
    assert "00:00:00,000 --> 00:00:04,000" in srt   # recortada al inicio del clip
    assert "00:00:04,000 --> 00:00:10,000" in srt   # recortada al final del clip
    assert "fuera del clip" not in srt


def test_ffmpeg_cmd_with_subtitles():
    vf = build_ffmpeg_cmd("in.mp4", 0, 10, "o.mp4", srt="/data/clip_1.srt")[9]
    assert "subtitles='/data/clip_1.srt'" in vf


def test_build_caption_dedupes_and_cleans_tags():
    cap = build_caption("Mi título", ["#IA", "ia", "data science", ""])
    assert cap == "Mi título #IA #datascience"


def test_plan_chunks_small_and_large():
    assert tiktok.plan_chunks(10 * tiktok.MB) == [(0, 10 * tiktok.MB - 1)]
    size = 100 * tiktok.MB
    ranges = tiktok.plan_chunks(size)
    assert ranges[0][0] == 0 and ranges[-1][1] == size - 1
    assert all(b[0] == a[1] + 1 for a, b in zip(ranges, ranges[1:]))  # contiguos
    assert all(e - s + 1 >= 5 * tiktok.MB for s, e in ranges)


def test_init_payload_modes():
    draft = tiktok.build_init_payload("draft", 1000, "x", "SELF_ONLY")
    assert "post_info" not in draft and draft["source_info"]["total_chunk_count"] == 1
    direct = tiktok.build_init_payload("direct", 1000, "cap", "SELF_ONLY")
    assert direct["post_info"]["title"] == "cap"
    assert direct["post_info"]["privacy_level"] == "SELF_ONLY"


def test_init_upload_parses_response(monkeypatch):
    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"data": {"publish_id": "p1", "upload_url": "https://u"}, "error": {"code": "ok"}}
    monkeypatch.setattr(tiktok.requests, "post", lambda *a, **k: R())
    assert tiktok.init_upload("tok", "draft", 1000, "c", "SELF_ONLY") == ("p1", "https://u")


def test_api_error_raises(monkeypatch):
    class R:
        def raise_for_status(self): pass
        def json(self): return {"error": {"code": "scope_not_authorized", "message": "no"}}
    monkeypatch.setattr(tiktok.requests, "post", lambda *a, **k: R())
    with pytest.raises(tiktok.TikTokError):
        tiktok.init_upload("tok", "draft", 1000, "c", "SELF_ONLY")


def test_status_mapping():
    assert status_to_clip_status("PUBLISH_COMPLETE") == "published"
    assert status_to_clip_status("PROCESSING_UPLOAD") == "processing"
