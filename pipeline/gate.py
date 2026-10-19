from pathlib import Path

from pipeline import state as st
from pipeline.checks import check_brief, check_prd

CHECKS = {
    "brief": ("brief.md", check_brief),
    "prd": ("prd.md", check_prd),
}


def blocking_issues(
    run_id: str, stage: str, runs_dir: Path = Path("runs")
) -> list[str]:
    if stage not in CHECKS:
        return []
    filename, checker = CHECKS[stage]
    path = st.run_dir(run_id, runs_dir) / filename
    if not path.exists():
        return [f"{filename} not found"]
    return checker(path.read_text())
