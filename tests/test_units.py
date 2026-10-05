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
