import contextlib

import pytest

from pipeline import state as st
from pipeline.revise import run_revise


class FakeLLM:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


@pytest.fixture
def setup(tmp_path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    d = st.run_dir(run.run_id, runs)
    (d / "prd.md").write_text("OLD PRD")
    prompt = tmp_path / "p.md"
    prompt.write_text("system")
    return runs, run, d, prompt, tmp_path / "missing.md"


def test_revise_sends_document_and_feedback(setup):
    runs, run, d, prompt, missing = setup
    llm = FakeLLM("NEW PRD")
    run_revise(run.run_id, "prd", "FIX THE PHONE RULE", llm, runs, prompt, missing)
    user = llm.calls[0][1]
    assert "OLD PRD" in user
    assert "FIX THE PHONE RULE" in user


def test_revise_archives_old_and_resets_status(setup):
    runs, run, d, prompt, missing = setup
    run_revise(run.run_id, "prd", "x", FakeLLM("NEW PRD"), runs, prompt, missing)
    assert (d / "prd.prev.md").read_text() == "OLD PRD"
    assert (d / "prd.md").read_text() == "NEW PRD\n"
    assert st.load(run.run_id, runs).stages["prd"] == "awaiting_approval"


def test_revise_rejects_unknown_stage(setup):
    runs, run, d, prompt, missing = setup
    with pytest.raises(ValueError):
        run_revise(run.run_id, "build", "x", FakeLLM("x"), runs, prompt, missing)


def test_revise_requires_existing_file(setup):
    runs, run, d, prompt, missing = setup
    with pytest.raises(ValueError):
        run_revise(run.run_id, "brief", "x", FakeLLM("x"), runs, prompt, missing)


def test_revise_repair_does_not_resend_old_document(tmp_path):
    from pipeline import state as st
    from pipeline.revise import run_revise

    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    run.stages["prd"] = "awaiting_approval"
    st.save(run, runs)
    (st.run_dir(run.run_id, runs) / "prd.md").write_text("OLD-DOC-MARKER " * 50)
    prompt = tmp_path / "p.md"
    prompt.write_text("prompt")
    seen: list[str] = []

    class Llm:
        def chat(self, system: str, user: str) -> str:
            seen.append(user)
            return "## Overview\nshort" if len(seen) == 1 else "x " * 5

    with contextlib.suppress(Exception):
        run_revise(
            run.run_id,
            "prd",
            "FEEDBACK-MARKER",
            Llm(),
            runs,
            prompt,
            tmp_path / "none.md",
        )
    assert len(seen) >= 2
    assert "OLD-DOC-MARKER" in seen[0]
    assert "OLD-DOC-MARKER" not in seen[1]
    assert "FEEDBACK-MARKER" in seen[1]
