import json
from pathlib import Path

from pipeline import state as st
from pipeline.review import Issue, make_chunks, prd_digest, run_review


class CountLLM:
    def __init__(self):
        self.calls = 0

    def chat(self, system: str, user: str) -> str:
        self.calls += 1
        return json.dumps({"issues": []})


def no_static(workspace: Path) -> list[Issue]:
    return []


def no_pause(seconds: float) -> None:
    return None


def setup(tmp_path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    base = st.run_dir(run.run_id, runs)
    (base / "prd.md").write_text("PRD TEXT")
    (base / "build" / "app").mkdir(parents=True)
    (base / "build" / "app" / "a.py").write_text("x" * 100)
    prompt = tmp_path / "p.md"
    prompt.write_text("system")
    return runs, run, prompt


def test_prd_digest_keeps_key_sections_only():
    prd = (
        "## Overview\nSKIP ME\n\n"
        "## Functional requirements\nREQ ONE\n\n"
        "## Acceptance criteria\nAC ONE\n\n"
        "## Milestones\nSKIP TOO\n"
    )
    out = prd_digest(prd)
    assert "REQ ONE" in out
    assert "AC ONE" in out
    assert "SKIP ME" not in out
    assert "SKIP TOO" not in out


def test_prd_digest_falls_back_to_whole_text():
    assert prd_digest("plain text") == "plain text"


def test_default_chunks_are_small(tmp_path):
    ws = tmp_path / "build"
    (ws / "app").mkdir(parents=True)
    for n in range(6):
        (ws / "app" / f"f{n}.py").write_text("x" * 2000)
    assert all(len(chunk) <= 5000 for chunk in make_chunks(ws))


def test_saved_results_are_reused(tmp_path):
    runs, run, prompt = setup(tmp_path)
    llm = CountLLM()
    run_review(run.run_id, llm, runs, prompt, no_static, no_pause, 0.0)
    assert llm.calls == 1
    run_review(run.run_id, llm, runs, prompt, no_static, no_pause, 0.0)
    assert llm.calls == 1
