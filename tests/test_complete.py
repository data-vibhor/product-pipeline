import pytest

from pipeline.complete import TASKS, complete_message, run_complete


def test_tasks_cover_the_missing_pieces():
    assert set(TASKS) == {"frontend", "tests", "docs"}


def test_every_task_forbids_commands_and_backend_changes():
    for text in TASKS.values():
        assert "Do not change its routes or behaviour" in text
        assert "Do not run any commands" in text


def test_tests_task_names_the_security_cases_and_deps():
    text = complete_message("tests")
    for word in ("CSRF", "another owner", "secret", "python-csv", "aiosqlite"):
        assert word in text


def test_unknown_task_is_rejected():
    with pytest.raises(ValueError):
        complete_message("nope")


def test_run_complete_passes_message_to_fixer():
    seen = []

    def fixer(run_id, message):
        seen.append((run_id, message))
        return None, True, None

    _run, ok, _work = run_complete("r1", "docs", fixer)
    assert ok
    assert seen == [("r1", TASKS["docs"])]


def test_frontend_task_follows_the_ux_spec():
    assert "UX.md" in complete_message("frontend")
