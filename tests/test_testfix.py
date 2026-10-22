import json
from pathlib import Path

from pipeline import state as st
from pipeline.testfix import (
    failure_lines,
    failure_report,
    fix_task,
    last_run_output,
    repair_until_green,
)


def quiet(text: str) -> None:
    return None


class FakeTester:
    def __init__(self, base: Path, outputs, extras=None):
        self.base = base
        self.outputs = list(outputs)
        self.extras = extras or []
        self.calls = 0

    def __call__(self, run_id: str) -> tuple[bool, str]:
        self.calls += 1
        if len(self.outputs) > 1:
            ok, text = self.outputs.pop(0)
        else:
            ok, text = self.outputs[0]
        log = "=== round 1: docker run (network off) ===\n" + text
        (self.base / "test.log").write_text(log)
        result = {"auto_added_requirements": self.extras}
        (self.base / "test-result.json").write_text(json.dumps(result))
        return ok, text


class FakeFixer:
    def __init__(self, ok: bool = True):
        self.ok = ok
        self.messages: list[str] = []

    def __call__(self, run_id: str, message: str):
        self.messages.append(message)
        return None, self.ok, Path("work")


def make(tmp_path: Path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    return runs, run.run_id, st.run_dir(run.run_id, runs)


def test_passing_tests_need_no_fixer(tmp_path):
    runs, run_id, base = make(tmp_path)
    tester, fixer = FakeTester(base, [(True, "1 passed")]), FakeFixer()
    assert repair_until_green(run_id, tester, fixer, runs, 3, quiet)
    assert fixer.messages == []


def test_failure_is_fixed_then_tests_pass(tmp_path):
    runs, run_id, base = make(tmp_path)
    outputs = [(False, "FAILED tests/a.py::t - boom\nE       boom"), (True, "ok")]
    tester, fixer = FakeTester(base, outputs), FakeFixer()
    assert repair_until_green(run_id, tester, fixer, runs, 3, quiet)
    assert tester.calls == 2
    assert len(fixer.messages) == 1
    assert "boom" in fixer.messages[0]


def test_missing_packages_are_passed_to_the_fixer(tmp_path):
    runs, run_id, base = make(tmp_path)
    outputs = [(False, "FAILED tests/a.py::t"), (True, "ok")]
    tester = FakeTester(base, outputs, extras=["pydantic[email]"])
    fixer = FakeFixer()
    repair_until_green(run_id, tester, fixer, runs, 3, quiet)
    assert "pydantic[email]" in fixer.messages[0]


def test_no_progress_first_widens_the_task_then_stops(tmp_path):
    runs, run_id, base = make(tmp_path)
    tester = FakeTester(base, [(False, "FAILED tests/a.py::t - boom")])
    fixer = FakeFixer()
    assert not repair_until_green(run_id, tester, fixer, runs, 5, quiet)
    assert tester.calls == 3
    assert len(fixer.messages) == 2
    assert "test setup" not in fixer.messages[0]
    assert "test setup" in fixer.messages[1]


def test_widened_task_is_dropped_once_progress_resumes(tmp_path):
    runs, run_id, base = make(tmp_path)
    outputs = [
        (False, "FAILED tests/a.py::t1 - x"),
        (False, "FAILED tests/a.py::t1 - x"),
        (False, "FAILED tests/a.py::t2 - y"),
        (True, "ok"),
    ]
    tester, fixer = FakeTester(base, outputs), FakeFixer()
    assert repair_until_green(run_id, tester, fixer, runs, 5, quiet)
    assert len(fixer.messages) == 3
    assert "test setup" in fixer.messages[1]
    assert "test setup" not in fixer.messages[2]


def test_stops_after_the_maximum_rounds(tmp_path):
    runs, run_id, base = make(tmp_path)
    outputs = [(False, f"FAILED tests/a.py::t{n} - x") for n in range(10)]
    tester, fixer = FakeTester(base, outputs), FakeFixer()
    assert not repair_until_green(run_id, tester, fixer, runs, 2, quiet)
    assert tester.calls == 3
    assert len(fixer.messages) == 2


def test_stops_when_the_test_run_finds_no_tests(tmp_path):
    runs, run_id, base = make(tmp_path)
    text = "PytestConfigWarning: No files were found in testpaths\n1 warning in 0.00s"
    tester, fixer = FakeTester(base, [(False, text)]), FakeFixer()
    assert not repair_until_green(run_id, tester, fixer, runs, 3, quiet)
    assert fixer.messages == []


def test_stops_when_the_fixer_fails(tmp_path):
    runs, run_id, base = make(tmp_path)
    tester = FakeTester(base, [(False, "FAILED tests/a.py::t")])
    fixer = FakeFixer(ok=False)
    assert not repair_until_green(run_id, tester, fixer, runs, 3, quiet)
    assert tester.calls == 1


def test_report_counts_repeated_error_lines():
    output = "E       same\nE       same\nE       same\nFAILED tests/a.py::t"
    assert "3x" in failure_report(output)


def test_failure_lines_are_deduplicated():
    output = "FAILED tests/a.py::t\nFAILED tests/a.py::t\nERROR tests/b.py::u"
    assert failure_lines(output) == ["FAILED tests/a.py::t", "ERROR tests/b.py::u"]


def test_only_the_last_test_run_is_used():
    log = (
        "=== round 1: docker run (network off) ===\nOLD\n"
        "=== round 2: docker run (network off) ===\nNEW"
    )
    result = last_run_output(log)
    assert "NEW" in result
    assert "OLD" not in result


def test_a_failed_last_build_uses_the_build_output():
    log = (
        "=== round 1: docker run (network off) ===\nold\n"
        "=== round 2: docker build ===\nBUILD ERR"
    )
    assert "BUILD ERR" in last_run_output(log)


def test_stuck_note_keeps_the_safety_rules():
    text = fix_task("REPORT", [], stuck=True)
    assert "fixtures" in text
    assert "never delete or skip tests" in text
    assert "Do not run any commands" in text


def test_fix_task_has_extras_and_safety_rules():
    text = fix_task("REPORT", ["pydantic[email]"])
    assert "pydantic[email]" in text
    assert "REPORT" in text
    assert "Do not run any commands" in text
    assert "never delete tests" in text
