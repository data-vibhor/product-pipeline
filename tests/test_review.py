import json
from pathlib import Path

import pytest

from pipeline import state as st
from pipeline.review import (
    Issue,
    make_chunks,
    parse_review,
    run_review,
    verdict_for,
)


class SeqLLM:
    def __init__(self, replies: list[str]):
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if len(self.replies) > 1:
            return self.replies.pop(0)
        return self.replies[0]


def no_static(workspace: Path) -> list[Issue]:
    return []


def issues_json(severity: str | None) -> str:
    if severity is None:
        return json.dumps({"issues": []})
    issue = {"severity": severity, "file": "app/main.py", "problem": "p", "fix": "f"}
    return json.dumps({"issues": [issue]})


def make_run(tmp_path: Path, with_build: bool = True):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    base = st.run_dir(run.run_id, runs)
    (base / "prd.md").write_text("PRD TEXT")
    if with_build:
        build = base / "build"
        (build / "app").mkdir(parents=True)
        (build / "app" / "main.py").write_text("print('x')")
        (build / "tests").mkdir()
        (build / "tests" / "test_x.py").write_text("SECRET TEST")
    prompt = tmp_path / "p.md"
    prompt.write_text("system")
    return runs, run, base, prompt


def test_verdict_levels():
    minor = Issue(severity="minor", problem="p")
    major = Issue(severity="major", problem="p")
    critical = Issue(severity="critical", problem="p")
    assert verdict_for([]) == "pass"
    assert verdict_for([minor]) == "pass"
    assert verdict_for([minor, major]) == "fix"
    assert verdict_for([major, critical]) == "block"


def test_chunks_split_and_skip_tests(tmp_path):
    ws = tmp_path / "build"
    (ws / "app").mkdir(parents=True)
    (ws / "tests").mkdir()
    for name in ("a.py", "b.py", "c.py"):
        (ws / "app" / name).write_text("x" * 100)
    (ws / "tests" / "test_a.py").write_text("SECRET")
    chunks = make_chunks(ws, max_chars=150)
    joined = "".join(chunks)
    assert len(chunks) == 3
    assert "SECRET" not in joined
    assert "=== FILE: app/a.py ===" in joined


def test_parse_review_accepts_fenced_json():
    text = "```json\n" + issues_json("minor") + "\n```"
    assert parse_review(text).issues[0].severity == "minor"


def test_pass_when_no_issues(tmp_path):
    runs, run, base, prompt = make_run(tmp_path)
    _, verdict = run_review(
        run.run_id, SeqLLM([issues_json(None)]), runs, prompt, no_static
    )
    assert verdict == "pass"
    assert (base / "review.json").exists()
    assert (base / "review.md").exists()
    assert st.load(run.run_id, runs).stages["review"] == "awaiting_approval"


def test_block_on_critical_issue(tmp_path):
    runs, run, base, prompt = make_run(tmp_path)
    _, verdict = run_review(
        run.run_id, SeqLLM([issues_json("critical")]), runs, prompt, no_static
    )
    assert verdict == "block"
    assert st.load(run.run_id, runs).stages["review"] == "failed"


def test_invalid_json_is_repaired(tmp_path):
    runs, run, base, prompt = make_run(tmp_path)
    llm = SeqLLM(["not json at all", issues_json(None)])
    _, verdict = run_review(run.run_id, llm, runs, prompt, no_static)
    assert verdict == "pass"
    assert len(llm.calls) == 2


def test_review_requires_a_build(tmp_path):
    runs, run, base, prompt = make_run(tmp_path, with_build=False)
    with pytest.raises(ValueError):
        run_review(run.run_id, SeqLLM([issues_json(None)]), runs, prompt, no_static)


def test_prompt_has_prd_and_code_but_not_tests(tmp_path):
    runs, run, base, prompt = make_run(tmp_path)
    llm = SeqLLM([issues_json(None)])
    run_review(run.run_id, llm, runs, prompt, no_static)
    user = llm.calls[0][1]
    assert "PRD TEXT" in user
    assert "app/main.py" in user
    assert "SECRET TEST" not in user
