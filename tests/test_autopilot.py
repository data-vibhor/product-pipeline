import json
from pathlib import Path

from pipeline import state as st
from pipeline.autopilot import COMPLETE_ORDER, autopilot


class FakeOps:
    def __init__(self, runs, run_id, test_results=(True,), issue_rounds=((),), fail_task=None):
        self.runs, self.run_id = runs, run_id
        self.test_results = list(test_results)
        self.issue_rounds = list(issue_rounds)
        self.fail_task = fail_task
        self.calls: list[str] = []

    def complete(self, task):
        self.calls.append(f"complete:{task}")
        return task != self.fail_task

    def test_fix(self):
        self.calls.append("test_fix")
        return self.test_results.pop(0) if len(self.test_results) > 1 else self.test_results[0]

    def review(self):
        self.calls.append("review")
        issues = self.issue_rounds.pop(0) if len(self.issue_rounds) > 1 else self.issue_rounds[0]
        path = st.run_dir(self.run_id, self.runs) / "review.json"
        path.write_text(json.dumps({"issues": [{"severity": s} for s in issues]}))
        return "block" if issues else "pass"

    def fix(self, numbers):
        self.calls.append(f"fix:{numbers}")
        return True

    browser_ok = True

    def browser_check(self):
        self.calls.append("browser_check")
        return self.browser_ok

    def deploy_kit(self):
        self.calls.append("deploy_kit")


def setup(tmp_path: Path, done: bool = True):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    build = st.run_dir(run.run_id, runs) / "build"
    for _, marker in COMPLETE_ORDER:
        if done:
            (build / marker).parent.mkdir(parents=True, exist_ok=True)
            (build / marker).write_text("x")
    build.mkdir(parents=True, exist_ok=True)
    return runs, run.run_id


def quiet(text):
    return None


def run(runs, run_id, ops):
    notes: list[tuple[str, str]] = []
    ok = autopilot(run_id, ops, quiet, lambda t, m: notes.append((t, m)), runs)
    return ok, notes


def test_happy_path_skips_done_work_and_deploys(tmp_path):
    runs, rid = setup(tmp_path)
    ops = FakeOps(runs, rid)
    ok, notes = run(runs, rid, ops)
    assert ok
    assert ops.calls == ["test_fix", "review", "browser_check", "deploy_kit"]
    assert notes[-1][0] == "Pipeline finished"


def test_missing_pieces_are_completed_in_order(tmp_path):
    runs, rid = setup(tmp_path, done=False)
    ops = FakeOps(runs, rid)
    run(runs, rid, ops)
    done = [c for c in ops.calls if c.startswith("complete:")]
    assert done == [f"complete:{t}" for t, _ in COMPLETE_ORDER]


def test_failed_task_stops_and_notifies(tmp_path):
    runs, rid = setup(tmp_path, done=False)
    ops = FakeOps(runs, rid, fail_task="tests")
    ok, notes = run(runs, rid, ops)
    assert not ok
    assert "complete:tests-more" not in ops.calls
    assert notes[-1][0] == "Pipeline stopped"


def test_failing_tests_stop_before_review(tmp_path):
    runs, rid = setup(tmp_path)
    ops = FakeOps(runs, rid, test_results=(False,))
    ok, _ = run(runs, rid, ops)
    assert not ok
    assert "review" not in ops.calls and "deploy_kit" not in ops.calls


def test_blocking_issues_are_fixed_then_retested(tmp_path):
    runs, rid = setup(tmp_path)
    ops = FakeOps(runs, rid, issue_rounds=(("critical", "minor", "major"), ()))
    ok, _ = run(runs, rid, ops)
    assert ok
    assert ops.calls == ["test_fix", "review", "fix:1,3", "test_fix", "review", "browser_check", "deploy_kit"]


def test_stops_when_blocking_issues_never_clear(tmp_path):
    runs, rid = setup(tmp_path)
    ops = FakeOps(runs, rid, issue_rounds=(("critical",),))
    ok, notes = run(runs, rid, ops)
    assert not ok
    assert "deploy_kit" not in ops.calls
    assert ops.calls.count("fix:1") == 2


def test_failed_browser_check_stops_before_deploy_kit(tmp_path):
    runs, run_id = setup(tmp_path)
    ops = FakeOps(runs, run_id)
    ops.browser_ok = False
    ok, notes = run(runs, run_id, ops)
    assert not ok and "browser_check" in ops.calls and "deploy_kit" not in ops.calls
    assert notes and "browser" in notes[0][1]
