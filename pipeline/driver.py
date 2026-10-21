from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pipeline import state as st
from pipeline.fix import load_issues
from pipeline.revise import STAGES

MAX_FIX_ROUNDS = 5

Ask = Callable[[str], str]
Say = Callable[[str], None]


@dataclass
class Steps:
    brief: Callable[[str], st.RunState]
    prd: Callable[[str], st.RunState]
    revise: Callable[[str, str, str], st.RunState]
    build: Callable[[str], st.RunState]
    review: Callable[[str], tuple[st.RunState, str]]
    fix: Callable[[str, str, str], tuple[st.RunState, bool, Path]]


def approval_loop(
    run_id: str, stage: str, steps: Steps, ask: Ask, say: Say, runs_dir: Path
) -> bool:
    filename, checker, _ = STAGES[stage]
    path = st.run_dir(run_id, runs_dir) / filename
    while True:
        issues = checker(path.read_text())
        say(f"\n{stage} is ready: {path}")
        if issues:
            say("Automatic checks FAILED: " + "; ".join(issues))
        else:
            say("Automatic checks passed")
        answer = ask("Approve (y), give feedback (f) or stop (q)? ").strip().lower()
        if answer == "y":
            if issues:
                say("Cannot approve while the checks fail. Give feedback or stop.")
                continue
            st.approve(run_id, stage, runs_dir)
            return True
        if answer == "f":
            feedback = ask("Feedback: ").strip()
            if feedback:
                steps.revise(run_id, stage, feedback)
            continue
        if answer == "q":
            return False
        say("Please type y, f or q")


def show_issues(run_id: str, runs_dir: Path, say: Say) -> None:
    for number, issue in enumerate(load_issues(run_id, runs_dir), start=1):
        say(f"{number}. [{issue['severity']}] {issue['file']}: {issue['problem']}")


def drive(
    run_id: str,
    steps: Steps,
    ask: Ask,
    say: Say,
    runs_dir: Path = Path("runs"),
) -> st.RunState:
    run = st.load(run_id, runs_dir)
    if run.stages["brief"] != "approved":
        if run.stages["brief"] != "awaiting_approval":
            say("The brief did not finish. Start a new run with run-all.")
            return run
        if not approval_loop(run_id, "brief", steps, ask, say, runs_dir):
            return st.load(run_id, runs_dir)
    run = st.load(run_id, runs_dir)
    if run.stages["prd"] != "approved":
        if run.stages["prd"] in ("pending", "failed"):
            say("Writing the PRD ...")
            steps.prd(run_id)
        if not approval_loop(run_id, "prd", steps, ask, say, runs_dir):
            return st.load(run_id, runs_dir)
    run = st.load(run_id, runs_dir)
    if run.stages["build"] != "approved":
        say("Building. This can take up to 20 minutes ...")
        run = steps.build(run_id)
        if run.stages["build"] != "approved":
            say("The build failed. See build.log in the run folder.")
            return run
    rounds = 0
    while True:
        say("Reviewing the code ...")
        run, verdict = steps.review(run_id)
        say(f"Review verdict: {verdict}")
        show_issues(run_id, runs_dir, say)
        if verdict == "pass":
            return run
        if rounds >= MAX_FIX_ROUNDS:
            say("Stopping after the maximum number of fix rounds.")
            return run
        while True:
            choice = ask(
                "Issue numbers to fix (for example 1,3-5), or press Enter to stop: "
            ).strip()
            if not choice:
                return run
            try:
                run, ok, _ = steps.fix(run_id, choice, "")
            except ValueError as err:
                say(str(err))
                continue
            break
        rounds += 1
        if not ok:
            say("The fix failed. See fix.log in the run folder.")
            return run
        say("Fix applied. Reviewing again ...")


def run_all(
    idea: str,
    steps: Steps,
    ask: Ask,
    say: Say,
    runs_dir: Path = Path("runs"),
) -> st.RunState:
    run = steps.brief(idea)
    say(f"Run id: {run.run_id}")
    return drive(run.run_id, steps, ask, say, runs_dir)
