import json
from pathlib import Path

import pytest

from pipeline import state as st
from pipeline.browsertest import browser_passed, env_from_example, run_browser_check


def make(tmp_path: Path, example: str | None = "APP_SECRET_KEY=\nAI_MODEL_NAME=some-model\nFRONTEND_URL=\n# note\nS3_KEY=abc\n"):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    build = st.run_dir(run.run_id, runs) / "build"
    build.mkdir(parents=True)
    (build / "pyproject.toml").write_text('[project]\nname = "x"\n')
    if example is not None:
        (build / ".env.example").write_text(example)
    return runs, run.run_id, build


def recorder(build_code=0, run_code=0, run_out="browser check: PASSED"):
    calls: list[list[str]] = []

    def runner(cmd, timeout):
        calls.append(cmd)
        if cmd[:2] == ["docker", "build"]:
            return build_code, "built"
        return run_code, run_out

    return runner, calls


def test_env_uses_dummies_for_secrets_and_forces_sqlite(tmp_path):
    _, _, build = make(tmp_path)
    env = env_from_example(build)
    assert env["APP_SECRET_KEY"] == "x" * 40
    assert env["S3_KEY"] == "x" * 40
    assert env["AI_MODEL_NAME"] == "some-model"
    assert env["FRONTEND_URL"] == "dummy"
    assert env["DATABASE_URL"].startswith("sqlite+aiosqlite")
    assert env["APP_ENV"] == "development"


def test_env_without_example_still_sets_the_database(tmp_path):
    _, _, build = make(tmp_path, example=None)
    assert env_from_example(build)["DATABASE_URL"].startswith("sqlite")


def test_passing_run_writes_result_and_uses_safe_docker_flags(tmp_path):
    runs, run_id, _ = make(tmp_path)
    runner, calls = recorder()
    ok, tail = run_browser_check(run_id, runner, runs)
    assert ok and "PASSED" in tail
    base = st.run_dir(run_id, runs)
    assert json.loads((base / "browser-result.json").read_text())["status"] == "passed"
    assert browser_passed(base)
    run_cmd = calls[-1]
    assert "--network" in run_cmd and run_cmd[run_cmd.index("--network") + 1] == "none"
    assert "--shm-size" in run_cmd and "--cap-drop" in run_cmd
    assert "DATABASE_URL=sqlite+aiosqlite:////tmp/browser.db" in run_cmd
    ctx = base / "browser-context"
    assert (ctx / "Dockerfile").exists() and (ctx / "_browsercrawl.py").exists()
    assert "uvicorn app.main:app" in (ctx / "_browser_run.sh").read_text()


def test_failing_run_is_failed_and_reports_the_tail(tmp_path):
    runs, run_id, _ = make(tmp_path)
    runner, _ = recorder(run_code=1, run_out="FAILED javascript_error: boom (on /today)\nbrowser check: FAILED")
    ok, tail = run_browser_check(run_id, runner, runs)
    assert not ok and "javascript_error" in tail
    assert not browser_passed(st.run_dir(run_id, runs))


def test_docker_build_failure_is_reported(tmp_path):
    runs, run_id, _ = make(tmp_path)
    runner, calls = recorder(build_code=1)
    ok, _ = run_browser_check(run_id, runner, runs)
    assert not ok and len(calls) == 1
    status = json.loads((st.run_dir(run_id, runs) / "browser-result.json").read_text())["status"]
    assert status == "build_failed"


def test_missing_module_is_added_and_retried(tmp_path):
    runs, run_id, _ = make(tmp_path)
    outputs = iter([(1, "ModuleNotFoundError: No module named 'jwt'"), (0, "browser check: PASSED")])

    def runner(cmd, timeout):
        return (0, "built") if cmd[:2] == ["docker", "build"] else next(outputs)

    ok, _ = run_browser_check(run_id, runner, runs)
    assert ok
    extras = json.loads((st.run_dir(run_id, runs) / "browser-result.json").read_text())["auto_added_requirements"]
    assert extras == ["pyjwt"]


def test_needs_a_build_with_pyproject(tmp_path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    with pytest.raises(ValueError, match="no build"):
        run_browser_check(run.run_id, recorder()[0], runs)
