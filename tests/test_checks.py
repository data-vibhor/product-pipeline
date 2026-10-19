from pipeline.checks import HEADINGS, check_brief


def make_brief(skip: str | None = None, extra: str = "") -> str:
    parts = [f"## {h}\ntext" for h in HEADINGS if h != skip]
    return "\n".join(parts) + extra


def test_good_brief_passes():
    assert check_brief(make_brief()) == []


def test_missing_heading_is_reported():
    issues = check_brief(make_brief(skip="Risks"))
    assert any("missing headings: Risks" in i for i in issues)


def test_wrong_order_is_reported():
    text = "\n".join(f"## {h}\ntext" for h in reversed(HEADINGS))
    assert any("out of order" in i for i in check_brief(text))


def test_em_dash_is_reported():
    assert any("em dash" in i for i in check_brief(make_brief(extra="\na \u2014 b")))


def test_too_long_is_reported():
    assert any("too long" in i for i in check_brief(make_brief(extra=" word" * 600)))


def test_too_many_mvp_bullets_is_reported():
    bullets = "\n".join(f"- item {n}" for n in range(6))
    text = make_brief().replace("## MVP scope\ntext", f"## MVP scope\n{bullets}")
    assert any("MVP scope has 6 bullets" in i for i in check_brief(text))


def test_spaced_en_dash_is_reported():
    assert any("en dash" in i for i in check_brief(make_brief(extra="\na \u2013 b")))


def test_spaced_en_dash_is_reported():
    assert any("en dash" in i for i in check_brief(make_brief(extra="\na \u2013 b")))
