from pipeline.review import make_chunks, split_body


def test_split_body_keeps_every_line():
    body = "".join(f"line {n}\n" for n in range(500))
    parts = split_body(body, 300)
    assert "".join(parts) == body
    assert all(len(part) <= 300 for part in parts)


def test_split_body_breaks_one_giant_line():
    parts = split_body("x" * 1000, 300)
    assert "".join(parts) == "x" * 1000
    assert all(len(part) <= 300 for part in parts)


def test_long_files_are_split_not_truncated(tmp_path):
    ws = tmp_path / "build"
    (ws / "app").mkdir(parents=True)
    body = "".join(f"line {n}\n" for n in range(1500))
    (ws / "app" / "big.py").write_text(body)
    chunks = make_chunks(ws)
    joined = "".join(chunks)
    assert len(chunks) > 1
    assert all(len(chunk) <= 5000 for chunk in chunks)
    assert "[truncated]" not in joined
    assert "line 1499" in joined
    assert "(part 1 of" in joined
