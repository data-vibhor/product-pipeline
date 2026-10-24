import json
from pathlib import Path

import pytest

from pipeline import state as st
from pipeline.testrun import DOCKERFILE, run_tests


class FakeRunner:
    def __init__(self, build_code: int = 0, test_code: int = 0):
        self.build_code = build_code
        self.test_code = test_code
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], timeout: int) -> tuple[int, str]:
        self.calls.append(cmd)
        if cmd[1] == "build":
            return self.build_code, "build output"
        return self.test_code, "1 passed" if self.test_code == 0 else "2 failed"


def make_run(tmp_path: Path, with_pyproject: bool = True):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    base = st.run_dir(run.run_id, runs)
    build = base / "build"
    (build / "app").mkdir(parents=True)
    (build / "app" / "main.py").write_text("x")
    if with_pyproject:
        (build / "pyproject.toml").write_text("[project]\nname='x'\n")
    (build / ".env").write_text("SECRET_KEY=abc")
    (build / "test.db").write_text("data")
    return runs, run, base


def read_result(base: Path) -> dict:
    return json.loads((base / "test-result.json").read_text())


def test_tests_pass_and_run_with_network_off(tmp_path):
    runs, run, base = make_run(tmp_path)
    runner = FakeRunner()
    ok, tail = run_tests(run.run_id, runner, runs)
    assert ok
    assert "--network" in runner.calls[1]
    assert "none" in runner.calls[1]
    assert "--network" not in runner.calls[0]
    assert read_result(base)["status"] == "passed"


def test_context_leaves_out_env_and_database(tmp_path):
    runs, run, base = make_run(tmp_path)
    run_tests(run.run_id, FakeRunner(), runs)
    ctx = base / "test-context"
    assert (ctx / "app" / "main.py").exists()
    assert (ctx / "Dockerfile").exists()
    assert (ctx / "_install_deps.py").exists()
    assert not (ctx / ".env").exists()
    assert not (ctx / "test.db").exists()


def test_failing_tests_report_failure(tmp_path):
    runs, run, base = make_run(tmp_path)
    ok, tail = run_tests(run.run_id, FakeRunner(test_code=1), runs)
    assert not ok
    assert "2 failed" in tail
    assert read_result(base)["status"] == "failed"


def test_build_failure_skips_the_test_run(tmp_path):
    runs, run, base = make_run(tmp_path)
    runner = FakeRunner(build_code=1)
    ok, tail = run_tests(run.run_id, runner, runs)
    assert not ok
    assert len(runner.calls) == 1
    assert read_result(base)["status"] == "build_failed"


def test_requires_a_build(tmp_path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    with pytest.raises(ValueError):
        run_tests(run.run_id, FakeRunner(), runs)


def test_requires_pyproject(tmp_path):
    runs, run, base = make_run(tmp_path, with_pyproject=False)
    with pytest.raises(ValueError):
        run_tests(run.run_id, FakeRunner(), runs)


def test_dependencies_are_installed_before_the_code_is_copied():
    assert DOCKERFILE.index("_install_deps.py") < DOCKERFILE.index("COPY . /app")


def test_fake_test_env_is_passed_only_to_the_test_run(tmp_path):
    runs, run, base = make_run(tmp_path)
    runner = FakeRunner()
    run_tests(run.run_id, runner, runs)
    assert any(arg.startswith("SECRET_KEY=test-only") for arg in runner.calls[1])
    assert not any("SECRET_KEY" in arg for arg in runner.calls[0])


def test_result_records_harness_extras(tmp_path):
    runs, run, base = make_run(tmp_path)
    run_tests(run.run_id, FakeRunner(), runs)
    assert "pytest-asyncio" in read_result(base)["harness_extras"]


def test_dockerfile_lints_for_undefined_names_before_tests():
    assert "ruff check --select F821,E9" in DOCKERFILE
    assert DOCKERFILE.index("ruff check") < DOCKERFILE.index("pytest")
