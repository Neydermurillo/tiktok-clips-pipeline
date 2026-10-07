from clips import publisher


def _items(n):
    return [{"clip_id": n, "file_path": "x.mp4", "caption": "Quizás 🍦 #fyp"}]


def test_queue_has_single_bom_and_readable_text(tmp_path, monkeypatch):
    monkeypatch.setattr(publisher, "CLIPS_DIR", tmp_path)
    publisher._write_manual_queue(_items(1))
    publisher._write_manual_queue(_items(2))  # segunda escritura: agrega, sin otro BOM ni otra cabecera
    raw = (tmp_path / "publish_queue.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf") and raw.count(b"\xef\xbb\xbf") == 1
    text = raw.decode("utf-8-sig")
    assert text.count("clip_id,file_path,caption") == 1
    assert text.count("Quizás 🍦 #fyp") == 2
