from pathlib import Path

from pipeline import state as st
from pipeline.constraints import CONSTRAINTS_FILE, with_constraints
from pipeline.llm import LLM
from pipeline.textutil import clean_text

PROMPT_FILE = Path("prompts/brief.md")


def run_brief(
    idea: str,
    llm: LLM,
    runs_dir: Path = Path("runs"),
    prompt_file: Path = PROMPT_FILE,
    constraints_file: Path = CONSTRAINTS_FILE,
) -> st.RunState:
    system = with_constraints(prompt_file.read_text(), constraints_file)
    run = st.new_run(idea, runs_dir)
    try:
        text = llm.chat(system, f"Product idea:\n{idea}")
    except Exception:
        run.stages["brief"] = "failed"
        st.save(run, runs_dir)
        raise
    out = st.run_dir(run.run_id, runs_dir) / "brief.md"
    out.write_text(clean_text(text).strip() + "\n")
    run.stages["brief"] = "awaiting_approval"
    st.save(run, runs_dir)
    return run
