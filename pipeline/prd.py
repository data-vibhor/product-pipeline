from pathlib import Path

from pipeline import state as st
from pipeline.checks import check_prd
from pipeline.constraints import CONSTRAINTS_FILE, with_constraints
from pipeline.llm import LLM
from pipeline.repair import generate_checked

PROMPT_FILE = Path("prompts/prd.md")


def run_prd(
    run_id: str,
    llm: LLM,
    runs_dir: Path = Path("runs"),
    prompt_file: Path = PROMPT_FILE,
    constraints_file: Path = CONSTRAINTS_FILE,
) -> st.RunState:
    run = st.load(run_id, runs_dir)
    if run.stages["brief"] != "approved":
        raise ValueError("The brief must be approved before writing the PRD")
    brief = (st.run_dir(run_id, runs_dir) / "brief.md").read_text()
    system = with_constraints(prompt_file.read_text(), constraints_file)
    try:
        text, _ = generate_checked(
            llm, system, f"Approved product brief:\n\n{brief}", check_prd
        )
    except Exception:
        run.stages["prd"] = "failed"
        st.save(run, runs_dir)
        raise
    out = st.run_dir(run_id, runs_dir) / "prd.md"
    if out.exists():
        out.replace(out.with_name("prd.prev.md"))
    out.write_text(text + "\n")
    run.stages["prd"] = "awaiting_approval"
    st.save(run, runs_dir)
    return run
