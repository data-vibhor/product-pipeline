import pytest

from pipeline import state as st
from pipeline.checks import PRD_HEADINGS, check_prd
from pipeline.prd import run_prd


class FakeLLM:
    def __init__(self, reply: str = "# PRD"):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


class BrokenLLM:
    def chat(self, system: str, user: str) -> str:
        raise RuntimeError("model down")


@pytest.fixture
def prompt(tmp_path):
    p = tmp_path / "prd_prompt.md"
    p.write_text("system prompt")
    return p


def make_run(runs, approved: bool = True):
    run = st.new_run("an idea", runs)
    (st.run_dir(run.run_id, runs) / "brief.md").write_text("BRIEF TEXT\n")
    if approved:
        run.stages["brief"] = "approved"
        st.save(run, runs)
    return run


def make_prd(criteria: int = 5) -> str:
    parts = []
    for h in PRD_HEADINGS:
        if h == "Acceptance criteria":
            items = "\n".join(f"- criterion {n}" for n in range(criteria))
            parts.append(f"## {h}\n{items}")
        else:
            parts.append(f"## {h}\ntext")
    return "\n".join(parts)


def test_prd_requires_approved_brief(tmp_path, prompt):
    runs = tmp_path / "runs"
    run = make_run(runs, approved=False)
    with pytest.raises(ValueError):
        run_prd(run.run_id, FakeLLM(), runs_dir=runs, prompt_file=prompt)


def test_prd_writes_file_and_waits_for_approval(tmp_path, prompt):
    runs = tmp_path / "runs"
    run = make_run(runs)
    llm = FakeLLM("# PRD\nbody")
    run_prd(run.run_id, llm, runs_dir=runs, prompt_file=prompt)
    out = runs / run.run_id / "prd.md"
    assert out.read_text() == "# PRD\nbody\n"
    assert st.load(run.run_id, runs).stages["prd"] == "awaiting_approval"
    assert "BRIEF TEXT" in llm.calls[0][1]


def test_prd_failure_marks_stage_failed(tmp_path, prompt):
    runs = tmp_path / "runs"
    run = make_run(runs)
    with pytest.raises(RuntimeError):
        run_prd(run.run_id, BrokenLLM(), runs_dir=runs, prompt_file=prompt)
    assert st.load(run.run_id, runs).stages["prd"] == "failed"


def test_good_prd_passes_check():
    assert check_prd(make_prd()) == []


def test_few_acceptance_criteria_are_flagged():
    issues = check_prd(make_prd(criteria=3))
    assert any("only 3 acceptance criteria" in i for i in issues)


def test_prd_missing_heading_is_flagged():
    text = make_prd().replace("## Milestones\ntext", "")
    assert any("missing headings: Milestones" in i for i in check_prd(text))
