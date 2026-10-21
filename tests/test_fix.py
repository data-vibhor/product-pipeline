import json
from pathlib import Path

import pytest

from pipeline import state as st
from pipeline.fix import fix_message, parse_numbers, run_fix

ISSUES = [
    {"severity": "critical", "file": "app.py", "problem": "PROBLEM ONE", "fix": "FIX ONE"},
    {"severity": "minor", "file": "app.py", "problem": "PROBLEM TWO", "fix": ""},
]


def make_run(tmp_path: Path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    base = st.run_dir(run.run_id, runs)
    (base / "prd.md").write_text("PRD TEXT")
    (base / "build").mkdir()
    (base / "build" / "app.py").write_text("old code")
    data = {"verdict": "block", "chunks": 1, "issues": ISSUES}
    (base / "review.json").write_text(json.dumps(data))
    return runs, run, base


def test_parse_numbers_accepts_lists_and_ranges():
    assert parse_numbers("1,3-4", 5) == [1, 3, 4]


def test_parse_numbers_rejects_out_of_range():
    with pytest.raises(ValueError):
        parse_numbers("9", 5)


def test_parse_numbers_rejects_empty():
    with pytest.raises(ValueError):
        parse_numbers(" , ", 5)


def test_fix_message_has_issue_note_and_safety_rules():
    text = fix_message([(1, ISSUES[0])], "NOTE TEXT")
    assert "PROBLEM ONE" in text
    assert "NOTE TEXT" in text
    assert "not an issue" in text
    assert "Do not run any commands" in text


def test_fix_runs_outside_and_copies_back(tmp_path):
    runs, run, base = make_run(tmp_path)
    ws = tmp_path / "ws"
    seen: list[str] = []

    def runner(message: str, cwd: Path) -> tuple[int, str]:
        seen.append(message)
        assert (cwd / "PRD.md").exists()
        (cwd / "app.py").write_text("new code")
        (cwd / "CHANGES.md").write_text("changed")
        return 0, "done"

    _, ok, work = run_fix(
        run.run_id, "1", "NOTE", runner, runs, tmp_path / "c.md", ws
    )
    assert ok
    assert work == ws / f"{run.run_id}-fix"
    assert (base / "build" / "app.py").read_text() == "new code"
    assert (base / "build.prev" / "app.py").read_text() == "old code"
    assert st.load(run.run_id, runs).stages["review"] == "pending"
    assert "PROBLEM ONE" in seen[0]
    assert "PROBLEM TWO" not in seen[0]


def test_failed_fix_keeps_original_build(tmp_path):
    runs, run, base = make_run(tmp_path)

    def runner(message: str, cwd: Path) -> tuple[int, str]:
        (cwd / "app.py").write_text("half done")
        return 1, "boom"

    _, ok, _ = run_fix(
        run.run_id, "1", "", runner, runs, tmp_path / "c.md", tmp_path / "ws"
    )
    assert not ok
    assert (base / "build" / "app.py").read_text() == "old code"


def test_fix_refuses_workspace_inside_git_repo(tmp_path):
    runs, run, base = make_run(tmp_path)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    def runner(message: str, cwd: Path) -> tuple[int, str]:
        return 0, ""

    with pytest.raises(RuntimeError):
        run_fix(
            run.run_id, "1", "", runner, runs, tmp_path / "c.md", repo / "ws"
        )


def test_fix_requires_review(tmp_path):
    runs, run, base = make_run(tmp_path)
    (base / "review.json").unlink()

    def runner(message: str, cwd: Path) -> tuple[int, str]:
        return 0, ""

    with pytest.raises(ValueError):
        run_fix(
            run.run_id, "1", "", runner, runs, tmp_path / "c.md", tmp_path / "ws"
        )
