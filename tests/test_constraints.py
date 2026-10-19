from pipeline import state as st
from pipeline.brief import run_brief
from pipeline.constraints import with_constraints
from pipeline.prd import run_prd


class FakeLLM:
    def __init__(self, reply: str = "reply"):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


def write(path, text):
    path.write_text(text)
    return path


def test_with_constraints_appends_text(tmp_path):
    c = write(tmp_path / "c.md", "NO PAID SERVICES")
    out = with_constraints("base prompt", c)
    assert out.startswith("base prompt")
    assert "NO PAID SERVICES" in out


def test_missing_constraints_file_is_harmless(tmp_path):
    assert with_constraints("base", tmp_path / "missing.md") == "base"


def test_brief_prompt_includes_constraints(tmp_path):
    prompt = write(tmp_path / "p.md", "system prompt")
    c = write(tmp_path / "c.md", "NO PAID SERVICES")
    llm = FakeLLM()
    run_brief(
        "idea",
        llm,
        runs_dir=tmp_path / "runs",
        prompt_file=prompt,
        constraints_file=c,
    )
    assert "NO PAID SERVICES" in llm.calls[0][0]


def test_prd_includes_constraints_and_archives_old_prd(tmp_path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    d = st.run_dir(run.run_id, runs)
    write(d / "brief.md", "BRIEF")
    write(d / "prd.md", "OLD PRD")
    run.stages["brief"] = "approved"
    st.save(run, runs)
    prompt = write(tmp_path / "p.md", "system prompt")
    c = write(tmp_path / "c.md", "NO PAID SERVICES")
    llm = FakeLLM("NEW PRD")
    run_prd(run.run_id, llm, runs_dir=runs, prompt_file=prompt, constraints_file=c)
    assert "NO PAID SERVICES" in llm.calls[0][0]
    assert (d / "prd.prev.md").read_text() == "OLD PRD"
    assert (d / "prd.md").read_text() == "NEW PRD\n"
