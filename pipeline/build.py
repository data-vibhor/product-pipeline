import shutil
import subprocess  # nosec B404
from collections.abc import Callable
from pathlib import Path

from pipeline import state as st
from pipeline.constraints import CONSTRAINTS_FILE

MODEL = "opencode/nemotron-3-ultra-free"
TIMEOUT_SECONDS = 1200
REFERENCE_FILES = {"PRD.md", "constraints.md"}

Runner = Callable[[str, Path], tuple[int, str]]


def opencode_runner(message: str, cwd: Path) -> tuple[int, str]:
    exe = shutil.which("opencode")
    if exe is None:
        raise RuntimeError("opencode was not found on PATH")
    try:
        proc = subprocess.run(  # nosec B603
            [exe, "run", "--model", MODEL, message],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, f"OpenCode timed out after {TIMEOUT_SECONDS} seconds"
    return proc.returncode, proc.stdout + proc.stderr


def build_message(prd: str, constraints: str) -> str:
    return (
        "You are building the MVP described in the PRD below.\n"
        "Work only inside the current folder and create every file here.\n"
        "Only create and edit files. Do not run any commands, do not install "
        "packages and do not use the network.\n\n"
        "Requirements:\n"
        "- Implement every functional requirement in the PRD.\n"
        "- Write pytest tests in a tests/ folder that cover the acceptance "
        "criteria. Tests must not need a running database or any external "
        "service; use fakes or an in-memory database.\n"
        "- Respect the founder constraints.\n"
        "- Provide pyproject.toml with dependencies, a README.md with run "
        "steps, and .env.example listing environment variables with no real "
        "secrets. Never hardcode secrets.\n"
        "- Where the PRD is unclear or unverified, choose the simplest option "
        "and record it in NOTES.md under 'Decisions and open questions'.\n\n"
        "PRD:\n\n" + prd + "\n\nFounder constraints:\n\n" + constraints
    )


def created_files(workspace: Path) -> list[Path]:
    return [
        p
        for p in workspace.rglob("*")
        if p.is_file()
        and p.relative_to(workspace).as_posix() not in REFERENCE_FILES
        and "__pycache__" not in p.parts
    ]


def run_build(
    run_id: str,
    runner: Runner = opencode_runner,
    runs_dir: Path = Path("runs"),
    constraints_file: Path = CONSTRAINTS_FILE,
) -> st.RunState:
    run = st.load(run_id, runs_dir)
    if run.stages["prd"] != "approved":
        raise ValueError("The PRD must be approved before building")
    base = st.run_dir(run_id, runs_dir)
    prd = (base / "prd.md").read_text()
    constraints = (
        constraints_file.read_text() if constraints_file.exists() else ""
    )
    workspace = base / "build"
    prev = base / "build.prev"
    if workspace.exists():
        if prev.exists():
            shutil.rmtree(prev)
        workspace.rename(prev)
    workspace.mkdir()
    (workspace / "PRD.md").write_text(prd)
    (workspace / "constraints.md").write_text(constraints)
    code, output = runner(build_message(prd, constraints), workspace)
    (base / "build.log").write_text(output)
    if code != 0 or not created_files(workspace):
        run.stages["build"] = "failed"
    else:
        run.stages["build"] = "approved"
    st.save(run, runs_dir)
    return run
