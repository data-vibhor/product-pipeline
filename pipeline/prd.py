from pathlib import Path

from pipeline import state as st
from pipeline.llm import LLM
from pipeline.textutil import clean_text

PROMPT_FILE = Path("prompts/prd.md")


def run_prd(
    run_id: str,
    llm: LLM,
    runs_dir: Path = Path("runs"),
    prompt_file: Path = PROMPT_FILE,
) -> st.RunState:
    run = st.load(run_id, runs_dir)
    if run.stages["brief"] != "approved":
        raise ValueError("The brief must be approved before writing the PRD")
    brief = (st.run_dir(run_id, runs_dir) / "brief.md").read_text()
    system = prompt_file.read_text()
    try:
        text = llm.chat(system, f"Approved product brief:\n\n{brief}")
    except Exception:
        run.stages["prd"] = "failed"
        st.save(run, runs_dir)
        raise
    out = st.run_dir(run_id, runs_dir) / "prd.md"
    out.write_text(clean_text(text).strip() + "\n")
    run.stages["prd"] = "awaiting_approval"
    st.save(run, runs_dir)
    return run
