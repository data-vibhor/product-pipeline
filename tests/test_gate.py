from pipeline import state as st
from pipeline.checks import HEADINGS
from pipeline.gate import blocking_issues


def test_gate_blocks_bad_brief(tmp_path):
    runs = tmp_path / "runs"
    run = st.new_run("x", runs)
    (st.run_dir(run.run_id, runs) / "brief.md").write_text("## Problem\ntext")
    assert blocking_issues(run.run_id, "brief", runs)


def test_gate_passes_good_brief(tmp_path):
    runs = tmp_path / "runs"
    run = st.new_run("x", runs)
    text = "\n".join(f"## {h}\ntext" for h in HEADINGS)
    (st.run_dir(run.run_id, runs) / "brief.md").write_text(text)
    assert blocking_issues(run.run_id, "brief", runs) == []


def test_gate_ignores_stages_without_checks(tmp_path):
    assert blocking_issues("any", "build", tmp_path) == []


def test_gate_reports_missing_file(tmp_path):
    runs = tmp_path / "runs"
    run = st.new_run("x", runs)
    issues = blocking_issues(run.run_id, "prd", runs)
    assert issues == ["prd.md not found"]
