import json
from pathlib import Path

from pipeline import state as st
from pipeline.checks import HEADINGS, PRD_HEADINGS
from pipeline.driver import Steps, drive, run_all


def good_brief() -> str:
    return "\n".join(f"## {h}\ntext" for h in HEADINGS)


def good_prd() -> str:
    parts = []
    for h in PRD_HEADINGS:
        if h == "Acceptance criteria":
            items = "\n".join(f"- item {n}" for n in range(5))
            parts.append(f"## {h}\n{items}")
        else:
            parts.append(f"## {h}\ntext")
    return "\n".join(parts)


def sink(text: str) -> None:
    return None


def scripted(answers):
    queue = list(answers)
    return lambda prompt: queue.pop(0)


class Fakes:
    def __init__(self, runs, verdicts=("pass",), brief_text=None, build_ok=True):
        self.runs = runs
        self.verdicts = list(verdicts)
        self.brief_text = good_brief() if brief_text is None else brief_text
        self.build_ok = build_ok
        self.calls: list[str] = []
        self.feedback: list[str] = []
        self.fixed: list[str] = []

    def brief(self, idea):
        self.calls.append("brief")
        run = st.new_run(idea, self.runs)
        (st.run_dir(run.run_id, self.runs) / "brief.md").write_text(self.brief_text)
        run.stages["brief"] = "awaiting_approval"
        st.save(run, self.runs)
        return run

    def prd(self, run_id):
        self.calls.append("prd")
        run = st.load(run_id, self.runs)
        (st.run_dir(run_id, self.runs) / "prd.md").write_text(good_prd())
        run.stages["prd"] = "awaiting_approval"
        st.save(run, self.runs)
        return run

    def revise(self, run_id, stage, feedback):
        self.calls.append("revise")
        self.feedback.append(feedback)
        run = st.load(run_id, self.runs)
        text = good_brief() if stage == "brief" else good_prd()
        filename = "brief.md" if stage == "brief" else "prd.md"
        (st.run_dir(run_id, self.runs) / filename).write_text(text)
        run.stages[stage] = "awaiting_approval"
        st.save(run, self.runs)
        return run

    def build(self, run_id):
        self.calls.append("build")
        run = st.load(run_id, self.runs)
        build = st.run_dir(run_id, self.runs) / "build"
        build.mkdir(exist_ok=True)
        (build / "app.py").write_text("x")
        run.stages["build"] = "approved" if self.build_ok else "failed"
        st.save(run, self.runs)
        return run

    def review(self, run_id):
        self.calls.append("review")
        if len(self.verdicts) > 1:
            verdict = self.verdicts.pop(0)
        else:
            verdict = self.verdicts[0]
        issue = {"severity": "major", "file": "app.py", "problem": "P", "fix": ""}
        data = {"verdict": verdict, "chunks": 1, "issues": [issue]}
        (st.run_dir(run_id, self.runs) / "review.json").write_text(json.dumps(data))
        return st.load(run_id, self.runs), verdict

    def fix(self, run_id, numbers, note):
        self.calls.append("fix")
        self.fixed.append(numbers)
        return st.load(run_id, self.runs), True, Path("work")

    def steps(self) -> Steps:
        return Steps(
            self.brief, self.prd, self.revise, self.build, self.review, self.fix
        )


def test_full_flow_to_a_passing_review(tmp_path):
    runs = tmp_path / "runs"
    f = Fakes(runs)
    run = run_all("idea", f.steps(), scripted(["y", "y"]), sink, runs)
    assert f.calls == ["brief", "prd", "build", "review"]
    state = st.load(run.run_id, runs)
    assert state.stages["brief"] == "approved"
    assert state.stages["prd"] == "approved"
    assert state.stages["build"] == "approved"


def test_feedback_is_applied_before_approval(tmp_path):
    runs = tmp_path / "runs"
    f = Fakes(runs)
    answers = ["f", "make it shorter", "y", "y"]
    run_all("idea", f.steps(), scripted(answers), sink, runs)
    assert f.feedback == ["make it shorter"]
    assert f.calls[:3] == ["brief", "revise", "prd"]


def test_cannot_approve_while_checks_fail(tmp_path):
    runs = tmp_path / "runs"
    f = Fakes(runs, brief_text="## Problem\ntext")
    run = run_all("idea", f.steps(), scripted(["y", "q"]), sink, runs)
    assert st.load(run.run_id, runs).stages["brief"] == "awaiting_approval"
    assert "prd" not in f.calls


def test_review_fix_loop(tmp_path):
    runs = tmp_path / "runs"
    f = Fakes(runs, verdicts=["fix", "pass"])
    run_all("idea", f.steps(), scripted(["y", "y", "1"]), sink, runs)
    assert f.calls == ["brief", "prd", "build", "review", "fix", "review"]
    assert f.fixed == ["1"]


def test_blank_answer_stops_after_review(tmp_path):
    runs = tmp_path / "runs"
    f = Fakes(runs, verdicts=["fix"])
    run_all("idea", f.steps(), scripted(["y", "y", ""]), sink, runs)
    assert "fix" not in f.calls


def test_failed_build_stops_before_review(tmp_path):
    runs = tmp_path / "runs"
    f = Fakes(runs, build_ok=False)
    run_all("idea", f.steps(), scripted(["y", "y"]), sink, runs)
    assert "review" not in f.calls


def test_resume_skips_approved_stages(tmp_path):
    runs = tmp_path / "runs"
    f = Fakes(runs)
    run = f.brief("idea")
    st.approve(run.run_id, "brief", runs)
    f.prd(run.run_id)
    st.approve(run.run_id, "prd", runs)
    f.calls.clear()
    drive(run.run_id, f.steps(), scripted([]), sink, runs)
    assert f.calls == ["build", "review"]
