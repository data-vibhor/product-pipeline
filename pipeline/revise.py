from pathlib import Path

from pipeline import state as st
from pipeline.checks import check_brief, check_prd
from pipeline.constraints import CONSTRAINTS_FILE, with_constraints
from pipeline.llm import LLM
from pipeline.repair import generate_checked

STAGES = {
    "brief": ("brief.md", check_brief, Path("prompts/brief.md")),
    "prd": ("prd.md", check_prd, Path("prompts/prd.md")),
}


def run_revise(
    run_id: str,
    stage: str,
    feedback: str,
    llm: LLM,
    runs_dir: Path = Path("runs"),
    prompt_file: Path | None = None,
    constraints_file: Path = CONSTRAINTS_FILE,
) -> st.RunState:
    if stage not in STAGES:
        raise ValueError(f"Cannot revise stage '{stage}'")
    filename, checker, default_prompt = STAGES[stage]
    run = st.load(run_id, runs_dir)
    path = st.run_dir(run_id, runs_dir) / filename
    if not path.exists():
        raise ValueError(f"{filename} does not exist yet")
    base = (prompt_file or default_prompt).read_text()
    system = with_constraints(base, constraints_file)
    user = (
        "Here is the current document:\n\n"
        + path.read_text()
        + "\n\nThe founder reviewed it and requires these changes:\n\n"
        + feedback
        + "\n\nApply every change. Keep everything else that is correct. "
        "Return the full revised document with the same headings."
    )
    try:
        # The repair prompt must not resend the old document: it would double the
        # request and exceed the provider's size limit.
        text, _ = generate_checked(
            llm,
            system,
            user,
            checker,
            repair_base="The founder required these changes to a document:\n\n"
            + feedback,
        )
    except Exception:
        run.stages[stage] = "failed"
        st.save(run, runs_dir)
        raise
    path.replace(path.with_name(f"{stage}.prev.md"))
    path.write_text(text + "\n")
    run.stages[stage] = "awaiting_approval"
    st.save(run, runs_dir)
    return run
