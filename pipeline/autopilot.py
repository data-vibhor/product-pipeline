"""Run the remaining pipeline stages unattended; stop only on a failure."""

import subprocess  # nosec B404
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pipeline import state as st
from pipeline.fix import load_issues

# (task, file in the build folder that shows the task is already done)
COMPLETE_ORDER = [
    ("frontend-core", "static/index.html"),
    ("frontend-invoices", "static/screens/invoices.js"),
    ("frontend-extras", "static/screens/reply.js"),
    ("tests", "tests/conftest.py"),
    ("tests-more", "tests/test_invoices.py"),
    ("hardening", "tests/test_hardening.py"),
    ("docs", "README.md"),
]
MAX_REVIEW_LOOPS = 2
BLOCKING = ("critical", "major")

Say = Callable[[str], None]


class Ops(Protocol):
    def complete(self, task: str) -> bool: ...
    def test_fix(self) -> bool: ...
    def review(self) -> str: ...
    def fix(self, numbers: str) -> bool: ...
    def browser_check(self) -> bool: ...
    def deploy_kit(self) -> None: ...


def notify_mac(title: str, message: str) -> None:
    if sys.platform != "darwin":
        return
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(  # nosec B603 B607
        ["osascript", "-e", script], check=False, capture_output=True
    )


def blocking_numbers(run_id: str, runs_dir: Path) -> list[int]:
    issues = load_issues(run_id, runs_dir)
    return [n for n, i in enumerate(issues, start=1) if i.get("severity") in BLOCKING]


def autopilot(
    run_id: str,
    ops: Ops,
    say: Say = print,
    notify: Callable[[str, str], None] = notify_mac,
    runs_dir: Path = Path("runs"),
) -> bool:
    build = st.run_dir(run_id, runs_dir) / "build"

    def stop(reason: str) -> bool:
        say(f"AUTOPILOT STOPPED: {reason}")
        notify("Pipeline stopped", reason)
        return False

    for task, marker in COMPLETE_ORDER:
        if (build / marker).exists():
            say(f"Skipping {task}: already done")
            continue
        say(f"Running {task} ...")
        if not ops.complete(task):
            return stop(f"{task} failed. See the fix logs in the run folder")
    for loop in range(MAX_REVIEW_LOOPS + 1):
        say("Running the test loop ...")
        if not ops.test_fix():
            return stop("tests still failing after the fix rounds")
        say("Reviewing the code ...")
        verdict = ops.review()
        numbers = blocking_numbers(run_id, runs_dir)
        say(f"Review verdict: {verdict}; critical or major issues: {len(numbers)}")
        if not numbers:
            break
        if loop == MAX_REVIEW_LOOPS:
            return stop("critical or major review issues remain after the fix loops")
        say("Fixing the critical and major issues ...")
        if not ops.fix(",".join(str(n) for n in numbers)):
            return stop("the review fix failed. See fix.log in the run folder")
    say("Crawling the app in a headless browser ...")
    if not ops.browser_check():
        return stop("the browser check failed. See browser.log in the run folder")
    say("Writing the deploy kit ...")
    ops.deploy_kit()
    say("AUTOPILOT DONE: tests pass and the review is clear. Ready to deploy.")
    notify("Pipeline finished", "Tests pass and the review is clear")
    return True


class RealOps:
    def __init__(self, run_id: str):
        self.run_id = run_id

    def complete(self, task: str) -> bool:
        from pipeline.complete import run_complete

        return bool(run_complete(self.run_id, task)[1])

    def test_fix(self) -> bool:
        from pipeline.fix import apply_fix
        from pipeline.testfix import repair_until_green, restore_previous
        from pipeline.testrun import run_tests

        note_file = st.run_dir(self.run_id) / "fixer-note.txt"
        note = note_file.read_text() if note_file.exists() else ""
        return repair_until_green(
            self.run_id,
            run_tests,
            lambda rid, message: apply_fix(rid, message, keep_partial=True),
            restore=restore_previous,
            note=note,
        )

    def review(self) -> str:
        from pipeline.llm import get_client
        from pipeline.review import run_review

        return run_review(self.run_id, get_client("groq"))[1]

    def fix(self, numbers: str) -> bool:
        from pipeline.fix import run_fix

        return bool(run_fix(self.run_id, numbers)[1])

    def browser_check(self) -> bool:
        from pipeline.browsertest import run_browser_check

        return run_browser_check(self.run_id)[0]

    def deploy_kit(self) -> None:
        from pipeline.deploy import write_kit

        write_kit(self.run_id, require_browser=True)
