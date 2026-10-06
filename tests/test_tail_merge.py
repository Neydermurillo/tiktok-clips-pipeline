from clips.segmentation import build_candidates

SEGS = [
    {"start": 0, "end": 10, "text": "hola"},
    {"start": 10, "end": 25, "text": "esto es una idea."},
    {"start": 25, "end": 40, "text": "otra idea"},
]


def test_short_tail_is_merged_into_last_window():
    out = build_candidates(SEGS, min_s=20, max_s=60, tail_max_s=90)
    assert len(out) == 1
    assert (out[0]["start_s"], out[0]["end_s"]) == (0, 40)
    assert out[0]["text"].endswith("otra idea")


def test_tail_is_dropped_when_merge_would_exceed_cap():
    out = build_candidates(SEGS, min_s=20, max_s=60, tail_max_s=30)
    assert [(o["start_s"], o["end_s"]) for o in out] == [(0, 25)]


def test_tail_dropped_when_disabled():
    assert build_candidates(SEGS, min_s=20, max_s=60, tail_max_s=0)[0]["end_s"] == 25


def test_video_like_the_reported_case():
    # transcripción 0–73.7 s: ventana de 65.7 s y cola de 8 s
    segs = [
        {"start": 0, "end": 30, "text": "Primera parte"},
        {"start": 30, "end": 65.7, "text": "Segunda parte."},
        {"start": 65.7, "end": 73.7, "text": "Cierre."},
    ]
    assert build_candidates(segs, min_s=20, max_s=60, tail_max_s=0)[0]["end_s"] == 65.7  # antes: cola perdida
    out = build_candidates(segs, min_s=20, max_s=60, tail_max_s=90)
    assert len(out) == 1 and out[0]["end_s"] == 73.7


def test_tail_without_previous_window_is_dropped():
    segs = [{"start": 0, "end": 8, "text": "muy corto"}]
    assert build_candidates(segs, min_s=20, max_s=60, tail_max_s=90) == []


def test_normal_windows_unchanged():
    segs = [{"start": 0, "end": 21, "text": "Uno."}, {"start": 21, "end": 45, "text": "Dos."}]
    out = build_candidates(segs, min_s=20, max_s=60, tail_max_s=90)
    assert [(o["start_s"], o["end_s"]) for o in out] == [(0, 21), (21, 45)]
