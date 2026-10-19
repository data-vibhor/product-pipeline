from pathlib import Path

from pipeline import state as st
from pipeline.llm import LLM

PROMPT_FILE = Path("prompts/brief.md")


def run_brief(
    idea: str,
    llm: LLM,
    runs_dir: Path = Path("runs"),
    prompt_file: Path = PROMPT_FILE,
) -> st.RunState:
    system = prompt_file.read_text()
    run = st.new_run(idea, runs_dir)
    try:
        text = llm.chat(system, f"Product idea:\n{idea}")
    except Exception:
        run.stages["brief"] = "failed"
        st.save(run, runs_dir)
        raise
    out = st.run_dir(run.run_id, runs_dir) / "brief.md"
    out.write_text(text.strip() + "\n")
    run.stages["brief"] = "awaiting_approval"
    st.save(run, runs_dir)
    return run
