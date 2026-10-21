import json
from pathlib import Path

from pipeline import state as st
from pipeline.testrun import MAX_DEP_ROUNDS, missing_requirements, run_tests


class SeqRunner:
    def __init__(self, run_outputs):
        self.run_outputs = list(run_outputs)
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], timeout: int) -> tuple[int, str]:
        self.calls.append(cmd)
        if cmd[1] == "build":
            return 0, "built"
        if len(self.run_outputs) > 1:
            return self.run_outputs.pop(0)
        return self.run_outputs[0]


def make_run(tmp_path: Path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    base = st.run_dir(run.run_id, runs)
    build = base / "build"
    (build / "app").mkdir(parents=True)
    (build / "app" / "main.py").write_text("x")
    (build / "pyproject.toml").write_text("[project]\nname='x'\n")
    return runs, run, base


def test_pip_hint_is_parsed():
    out = "ImportError: email-validator is not installed, run `pip install 'pydantic[email]'`"
    assert missing_requirements(out) == ["pydantic[email]"]


def test_module_names_are_mapped_to_packages():
    out = "ModuleNotFoundError: No module named 'jose'\nNo module named 'foo'\nNo module named 'app.main'"
    assert missing_requirements(out) == ["python-jose[cryptography]", "foo"]


def test_pip_flags_are_not_mistaken_for_packages():
    assert missing_requirements("pip install --no-cache-dir something") == []


def test_missing_package_is_added_and_the_tests_retried(tmp_path):
    runs, run, base = make_run(tmp_path)
    runner = SeqRunner(
        [(1, "run `pip install 'pydantic[email]'`"), (0, "1 passed")]
    )
    ok, tail = run_tests(run.run_id, runner, runs)
    assert ok
    assert len(runner.calls) == 4
    assert "pydantic[email]" in tail
    extras = (base / "test-context" / "_extra_requirements.txt").read_text()
    assert "pydantic[email]" in extras
    result = json.loads((base / "test-result.json").read_text())
    assert result["auto_added_requirements"] == ["pydantic[email]"]
    assert result["rounds"] == 2
    assert (base / "suggested-dependencies.txt").exists()


def test_real_test_failures_are_not_retried(tmp_path):
    runs, run, base = make_run(tmp_path)
    runner = SeqRunner([(1, "assert 1 == 2")])
    ok, tail = run_tests(run.run_id, runner, runs)
    assert not ok
    assert len(runner.calls) == 2
    assert "assert 1 == 2" in tail


def test_stops_after_the_maximum_number_of_rounds(tmp_path):
    runs, run, base = make_run(tmp_path)
    outputs = [(1, f"No module named 'pkg{n}'") for n in range(20)]
    runner = SeqRunner(outputs)
    ok, tail = run_tests(run.run_id, runner, runs)
    assert not ok
    assert len(runner.calls) == 2 * MAX_DEP_ROUNDS
