from pathlib import Path

import pytest

from pipeline import state as st
from pipeline.build import run_build


def make_run(runs: Path, prd_approved: bool = True) -> st.RunState:
    run = st.new_run("idea", runs)
    (st.run_dir(run.run_id, runs) / "prd.md").write_text("PRD TEXT")
    if prd_approved:
        run.stages["prd"] = "approved"
        st.save(run, runs)
    return run


def good_runner(message: str, cwd: Path) -> tuple[int, str]:
    (cwd / "app.py").write_text("print('hi')")
    return 0, "done"


def empty_runner(message: str, cwd: Path) -> tuple[int, str]:
    return 0, "wrote nothing"


def failing_runner(message: str, cwd: Path) -> tuple[int, str]:
    (cwd / "app.py").write_text("x")
    return 1, "boom"


def test_build_requires_approved_prd(tmp_path):
    runs = tmp_path / "runs"
    run = make_run(runs, prd_approved=False)
    with pytest.raises(ValueError):
        run_build(run.run_id, good_runner, runs, tmp_path / "c.md")


def test_successful_build_is_marked_approved(tmp_path):
    runs = tmp_path / "runs"
    run = make_run(runs)
    run_build(run.run_id, good_runner, runs, tmp_path / "c.md")
    assert st.load(run.run_id, runs).stages["build"] == "approved"
    assert (st.run_dir(run.run_id, runs) / "build" / "app.py").exists()
    assert (st.run_dir(run.run_id, runs) / "build.log").read_text() == "done"


def test_prompt_contains_prd_and_constraints(tmp_path):
    runs = tmp_path / "runs"
    run = make_run(runs)
    constraints = tmp_path / "c.md"
    constraints.write_text("NO PAID SERVICES")
    seen: list[str] = []

    def spy(message: str, cwd: Path) -> tuple[int, str]:
        seen.append(message)
        (cwd / "app.py").write_text("x")
        return 0, ""

    run_build(run.run_id, spy, runs, constraints)
    assert "PRD TEXT" in seen[0]
    assert "NO PAID SERVICES" in seen[0]


def test_build_with_no_files_is_failed(tmp_path):
    runs = tmp_path / "runs"
    run = make_run(runs)
    run_build(run.run_id, empty_runner, runs, tmp_path / "c.md")
    assert st.load(run.run_id, runs).stages["build"] == "failed"


def test_nonzero_exit_is_failed(tmp_path):
    runs = tmp_path / "runs"
    run = make_run(runs)
    run_build(run.run_id, failing_runner, runs, tmp_path / "c.md")
    assert st.load(run.run_id, runs).stages["build"] == "failed"


def test_rebuild_keeps_previous_build(tmp_path):
    runs = tmp_path / "runs"
    run = make_run(runs)
    run_build(run.run_id, good_runner, runs, tmp_path / "c.md")
    run_build(run.run_id, good_runner, runs, tmp_path / "c.md")
    base = st.run_dir(run.run_id, runs)
    assert (base / "build.prev" / "app.py").exists()
    assert (base / "build" / "app.py").exists()
