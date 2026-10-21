import json
import shutil
from pathlib import Path

from pipeline import state as st
from pipeline.build import (
    IGNORED,
    Runner,
    default_workspace_root,
    inside_git_repo,
    opencode_runner,
)
from pipeline.constraints import CONSTRAINTS_FILE


def parse_numbers(text: str, limit: int) -> list[int]:
    numbers: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            low, high = part.split("-", 1)
            span = range(int(low), int(high) + 1)
        else:
            span = range(int(part), int(part) + 1)
        for number in span:
            if number < 1 or number > limit:
                raise ValueError(f"Issue number {number} is out of range (1-{limit})")
            numbers.add(number)
    if not numbers:
        raise ValueError("No issue numbers given")
    return sorted(numbers)


def load_issues(run_id: str, runs_dir: Path = Path("runs")) -> list[dict]:
    path = st.run_dir(run_id, runs_dir) / "review.json"
    if not path.exists():
        raise ValueError("Run the review first")
    return json.loads(path.read_text())["issues"]


def fix_message(chosen: list[tuple[int, dict]], note: str) -> str:
    listed = "\n".join(
        f"{n}. [{i['severity']}] {i['file']}: {i['problem']}"
        + (f" Suggested fix: {i['fix']}" if i.get("fix") else "")
        for n, i in chosen
    )
    text = (
        "This folder holds an existing app. Read PRD.md and constraints.md first.\n"
        "Fix only the issues listed below.\n"
        "A reviewer saw only part of the project at a time and can be wrong. "
        "Before changing anything for an issue, check the code. If the issue is "
        "not real, leave the code alone and record 'not an issue' with the "
        "reason in CHANGES.md.\n"
        "For every real fix, add or update pytest tests in tests/. Tests must "
        "not need a database or the network.\n"
        "Only create and edit files. Do not run any commands, do not install "
        "packages and do not use the network. Do not rewrite files that the "
        "issues do not involve. Never hardcode secrets.\n"
        "Record each change in CHANGES.md: issue number, what changed and "
        "which files.\n\nIssues:\n" + listed + "\n"
    )
    if note.strip():
        text += "\nFounder instruction, which takes priority:\n" + note.strip() + "\n"
    return text


def tree_signature(path: Path) -> list[tuple[str, int, int]]:
    items: list[tuple[str, int, int]] = []
    for p in sorted(path.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            stat = p.stat()
            items.append((p.relative_to(path).as_posix(), stat.st_size, stat.st_mtime_ns))
    return items


def apply_fix(
    run_id: str,
    message: str,
    runner: Runner = opencode_runner,
    runs_dir: Path = Path("runs"),
    constraints_file: Path = CONSTRAINTS_FILE,
    workspace_root: Path | None = None,
) -> tuple[st.RunState, bool, Path]:
    run = st.load(run_id, runs_dir)
    base = st.run_dir(run_id, runs_dir)
    build_dir = base / "build"
    if not build_dir.exists():
        raise ValueError("There is no build to fix")
    root = workspace_root or default_workspace_root()
    if inside_git_repo(root):
        raise RuntimeError(
            f"{root} is inside a git repository. Fixes must run outside any repo"
        )
    root.mkdir(parents=True, exist_ok=True)
    work = root / f"{run_id}-fix"
    prev_work = root / f"{run_id}-fix.prev"
    if work.exists():
        if prev_work.exists():
            shutil.rmtree(prev_work)
        work.rename(prev_work)
    shutil.copytree(build_dir, work, ignore=IGNORED)
    (work / "PRD.md").write_text((base / "prd.md").read_text())
    constraints = constraints_file.read_text() if constraints_file.exists() else ""
    (work / "constraints.md").write_text(constraints)
    before = tree_signature(build_dir)
    code, output = runner(message, work)
    (base / "fix.log").write_text(output)
    if tree_signature(build_dir) != before:
        raise RuntimeError(
            "The build folder changed while the fixer ran in a separate folder. "
            f"Check {build_dir} before continuing"
        )
    if code != 0:
        return run, False, work
    prev = base / "build.prev"
    if prev.exists():
        shutil.rmtree(prev)
    build_dir.rename(prev)
    shutil.copytree(work, build_dir, ignore=IGNORED)
    run.stages["review"] = "pending"
    st.save(run, runs_dir)
    return run, True, work


def run_fix(
    run_id: str,
    numbers: str,
    note: str = "",
    runner: Runner = opencode_runner,
    runs_dir: Path = Path("runs"),
    constraints_file: Path = CONSTRAINTS_FILE,
    workspace_root: Path | None = None,
) -> tuple[st.RunState, bool, Path]:
    issues = load_issues(run_id, runs_dir)
    chosen = [(n, issues[n - 1]) for n in parse_numbers(numbers, len(issues))]
    return apply_fix(
        run_id,
        fix_message(chosen, note),
        runner,
        runs_dir,
        constraints_file,
        workspace_root,
    )
