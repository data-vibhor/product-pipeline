from pathlib import Path

from bakeoff.harness import (
    candidate_message,
    prepare_candidate,
    run_candidate,
    score_suite,
)
from bakeoff.mutations import MUTATIONS


def make_app(root: Path) -> Path:
    app = root / "app0"
    (app / "app").mkdir(parents=True)
    (app / "app" / "x.py").write_text("VALUE = 1\n")
    (app / "tests").mkdir()
    (app / "tests" / "test_x.py").write_text("def test_x():\n    pass\n")
    (app / "PRD.md").write_text("the prd")
    return app


def fake_runner(cmd, cwd, timeout):
    text = (cwd / "app" / "x.py").read_text()
    return (1, "fail") if "VALUE = 2" in text else (0, "ok")


def test_mutation_catalogue_is_complete_and_unique():
    names = [m[0] for m in MUTATIONS]
    assert len(names) == 24
    assert len(set(names)) == 24
    assert all(old != new for _, _, old, new in MUTATIONS)


def test_score_counts_killed_survived_and_bad_patch(tmp_path):
    app = make_app(tmp_path)
    muts = [
        ("kills", "app/x.py", "VALUE = 1", "VALUE = 2"),
        ("survives", "app/x.py", "VALUE = 1", "VALUE = 3"),
        ("bad", "app/x.py", "NOT THERE", "y"),
    ]
    s = score_suite(app, "python", tmp_path / "w", muts, runner=fake_runner, workers=1)
    assert s.clean_passed
    assert [r[1] for r in s.results] == ["KILLED", "SURVIVED", "BAD PATCH"]
    assert s.summary() == "killed 1 of 2"


def test_failing_clean_suite_is_invalid_and_runs_no_mutants(tmp_path):
    app = make_app(tmp_path)
    s = score_suite(app, "python", tmp_path / "w", runner=lambda c, d, t: (1, "boom"))
    assert not s.clean_passed
    assert s.results == []
    assert s.summary().startswith("INVALID")


def test_prepare_candidate_drops_existing_tests(tmp_path):
    app = make_app(tmp_path)
    ws = prepare_candidate(app, "prd text", tmp_path / "ws")
    assert (ws / "app" / "x.py").exists()
    assert list((ws / "tests").iterdir()) == []
    assert (ws / "PRD.md").read_text() == "prd text"


def test_candidate_message_has_prd_and_limits():
    msg = candidate_message("MY PRD")
    assert "MY PRD" in msg
    assert "Do not edit the app" in msg
    assert "CSRF" in msg


def test_run_candidate_no_tests_written(tmp_path):
    app = make_app(tmp_path)
    out = run_candidate("m/x", app, "python", tmp_path / "out", lambda m, msg, cwd: (0, "log"))
    assert out["status"] == "no tests written"


def test_run_candidate_scores_written_tests(tmp_path):
    app = make_app(tmp_path)

    def model(m, msg, cwd):
        (cwd / "tests" / "test_new.py").write_text("def test_a():\n    pass\n")
        return 0, "log"

    out = run_candidate("m/x", app, "python", tmp_path / "out", model, fake_runner)
    assert out["test_files"] == 1
    assert out["status"].startswith("killed 0 of")
