import json
from pathlib import Path

import pytest

from pipeline import state as st
from pipeline.fix import run_fix


def make_run(tmp_path: Path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    base = st.run_dir(run.run_id, runs)
    (base / "prd.md").write_text("PRD TEXT")
    (base / "build").mkdir()
    (base / "build" / "app.py").write_text("old code")
    issues = [{"severity": "major", "file": "app.py", "problem": "P", "fix": ""}]
    (base / "review.json").write_text(json.dumps({"issues": issues}))
    return runs, run, base


def test_fix_detects_edits_to_original_build(tmp_path):
    runs, run, base = make_run(tmp_path)

    def sneaky(message: str, cwd: Path) -> tuple[int, str]:
        (base / "build" / "app.py").write_text("edited in place")
        return 0, ""

    with pytest.raises(RuntimeError):
        run_fix(run.run_id, "1", "", sneaky, runs, tmp_path / "c.md", tmp_path / "ws")
