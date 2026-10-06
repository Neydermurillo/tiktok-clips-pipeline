import pytest

from clips import ingest, weights


# ---------- videos locales ----------
def test_resolve_local_relative_and_absolute(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "VIDEOS_DIR", tmp_path)
    assert ingest.resolve_local("file:a.mp4") == tmp_path / "a.mp4"
    absolute = tmp_path / "otro" / "b.mp4"
    assert ingest.resolve_local(f"file:{absolute}") == absolute


def test_resolve_local_empty():
    with pytest.raises(ValueError):
        ingest.resolve_local("file:  ")


def test_register_local_missing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "VIDEOS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        ingest.register_local("file:no_existe.mp4")


def test_register_local_requires_audio(tmp_path, monkeypatch):
    (tmp_path / "mudo.mp4").write_bytes(b"x")
    monkeypatch.setattr(ingest, "VIDEOS_DIR", tmp_path)
    monkeypatch.setattr(ingest, "has_audio", lambda p: False)
    with pytest.raises(RuntimeError):
        ingest.register_local("file:mudo.mp4")


def test_register_local_ok(tmp_path, monkeypatch):
    (tmp_path / "mi_video.mp4").write_bytes(b"x")
    monkeypatch.setattr(ingest, "VIDEOS_DIR", tmp_path)
    monkeypatch.setattr(ingest, "has_audio", lambda p: True)
    assert ingest.register_local("file:mi_video.mp4") == ("mi_video", str(tmp_path / "mi_video.mp4"))


def test_ingest_mixes_local_and_urls(monkeypatch):
    monkeypatch.setattr(ingest, "read_sources", lambda path=None: ["file:v.mp4", "https://youtu.be/x"])
    inserted = []
    monkeypatch.setattr(ingest.db, "query", lambda sql, params=None: [{"source_url": "file:ya.mp4"}])
    monkeypatch.setattr(ingest.db, "execute", lambda sql, params=None: inserted.append(params))
    monkeypatch.setattr(ingest, "register_local", lambda e: ("v", "data/videos/v.mp4"))
    monkeypatch.setattr(ingest, "download", lambda u: ("Titulo", "data/videos/x.mp4"))
    assert ingest.ingest_new_videos() == 2
    assert inserted == [("file:v.mp4", "v", "data/videos/v.mp4"), ("https://youtu.be/x", "Titulo", "data/videos/x.mp4")]


def test_ingest_skips_known_local(monkeypatch):
    monkeypatch.setattr(ingest, "read_sources", lambda path=None: ["file:ya.mp4"])
    monkeypatch.setattr(ingest.db, "query", lambda sql, params=None: [{"source_url": "file:ya.mp4"}])
    assert ingest.ingest_new_videos() == 0


# ---------- importancia de la IA ----------
def test_ai_weight_override_sets_both_weights(monkeypatch):
    monkeypatch.setenv("AI_WEIGHT", "0.8")
    monkeypatch.setattr(weights.db, "query", lambda *a, **k: pytest.fail("no debe consultar la base"))
    assert weights.current_weights() == (pytest.approx(0.2), 0.8)


def test_ai_weight_zero_and_one_are_valid(monkeypatch):
    monkeypatch.setenv("AI_WEIGHT", "0")
    assert weights.current_weights() == (1.0, 0.0)
    monkeypatch.setenv("AI_WEIGHT", "1")
    assert weights.current_weights() == (0.0, 1.0)


@pytest.mark.parametrize("bad", ["abc", "1.5", "-0.1"])
def test_ai_weight_invalid(monkeypatch, bad):
    monkeypatch.setenv("AI_WEIGHT", bad)
    with pytest.raises(ValueError):
        weights.current_weights()


def test_without_override_uses_stored(monkeypatch):
    monkeypatch.delenv("AI_WEIGHT", raising=False)
    monkeypatch.setattr(weights.db, "query", lambda sql, params=None: [{"w_rule": 0.3, "w_ai": 0.7}])
    assert weights.current_weights() == (0.3, 0.7)
