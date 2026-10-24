import pytest

from pipeline.complete import TASKS, complete_message, run_complete


def test_tasks_cover_the_missing_pieces():
    assert set(TASKS) == {"frontend-core", "frontend-invoices", "frontend-extras", "tests", "tests-more", "docs"}


def test_every_task_forbids_commands():
    for text in TASKS.values():
        assert "do not run" in text.lower()


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


def test_frontend_tasks_use_the_contracts_and_skip_the_backend():
    for name in ("frontend-core", "frontend-invoices", "frontend-extras"):
        text = complete_message(name)
        assert "UX.md and API.md" in text
        assert "Do not read the backend" in text


def test_run_complete_keeps_a_log_per_task(tmp_path):
    run = tmp_path / "r1"
    run.mkdir()
    (run / "fix.log").write_text("log text")
    run_complete("r1", "docs", lambda r, m: (None, True, None), runs_dir=tmp_path)
    assert (run / "fix-docs.log").read_text() == "log text"
