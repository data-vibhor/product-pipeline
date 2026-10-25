from pipeline.browsercrawl import DESTRUCTIVE, is_bug_response, key_of, value_for

ORIGIN = "http://localhost:8000"


def test_values_match_the_field():
    assert value_for("email", "email", "ab").endswith("@example.com")
    assert value_for("password", "password", "ab")
    assert value_for("tel", "phone", "ab").startswith("+91")
    assert value_for("text", "amount", "ab") == "125000"
    assert value_for("date", "due_date", "ab") == "2026-12-31"
    assert value_for("text", "name", "ab") == "Test ab"


def test_server_errors_and_missing_assets_are_bugs():
    assert is_bug_response("GET", 500, ORIGIN + "/invoices", ORIGIN)
    assert is_bug_response("GET", 404, ORIGIN + "/static/app.js", ORIGIN)
    assert is_bug_response("POST", 422, ORIGIN + "/auth/signup", ORIGIN)


def test_signed_out_checks_and_external_calls_are_not_bugs():
    assert not is_bug_response("GET", 401, ORIGIN + "/auth/me", ORIGIN)
    assert not is_bug_response("GET", 200, ORIGIN + "/x", ORIGIN)
    assert not is_bug_response("GET", 500, "https://fonts.example.com/a.css", ORIGIN)
    assert not is_bug_response("POST", 429, ORIGIN + "/x", ORIGIN)


def test_destructive_controls_are_recognised():
    for text in ("Delete account", "Log out", "Sign out", "Remove"):
        assert DESTRUCTIVE.search(text)
    assert not DESTRUCTIVE.search("Save invoice")


def test_control_key_is_stable():
    c = {"tag": "button", "text": "Save", "id": "s", "href": ""}
    assert key_of(c) == key_of(dict(c))
