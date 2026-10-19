import pytest

from pipeline import state as st
from pipeline.brief import run_brief


class FakeLLM:
    def __init__(self, reply: str = "# Brief"):
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
    p = tmp_path / "prompt.md"
    p.write_text("system prompt")
    return p


def test_brief_writes_file_and_waits_for_approval(tmp_path, prompt):
    runs = tmp_path / "runs"
    llm = FakeLLM("# Brief\nbody")
    run = run_brief("an idea", llm, runs_dir=runs, prompt_file=prompt)
    assert (runs / run.run_id / "brief.md").read_text() == "# Brief\nbody\n"
    assert st.load(run.run_id, runs).stages["brief"] == "awaiting_approval"
    assert "an idea" in llm.calls[0][1]


def test_failure_marks_stage_failed(tmp_path, prompt):
    runs = tmp_path / "runs"
    with pytest.raises(RuntimeError):
        run_brief("an idea", BrokenLLM(), runs_dir=runs, prompt_file=prompt)
    run_id = next(runs.iterdir()).name
    assert st.load(run_id, runs).stages["brief"] == "failed"


def test_approve_only_after_brief_is_ready(tmp_path, prompt):
    runs = tmp_path / "runs"
    early = st.new_run("x", runs)
    with pytest.raises(ValueError):
        st.approve(early.run_id, "brief", runs)
    run = run_brief("an idea", FakeLLM(), runs_dir=runs, prompt_file=prompt)
    assert st.approve(run.run_id, "brief", runs).stages["brief"] == "approved"
