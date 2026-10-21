import json
import re
from collections import Counter
from collections.abc import Callable
from pathlib import Path

from pipeline import state as st

MAX_ROUNDS = 3
REPORT_CHARS = 6000
RUN_MARKER = re.compile(r"^=== round \d+: docker run.*$", re.MULTILINE)
BUILD_MARKER = re.compile(r"^=== round \d+: docker build.*$", re.MULTILINE)
SUMMARY_LINE = re.compile(r"^(FAILED|ERROR) \S+")
ERROR_LINE = re.compile(r"^E\s{2,}\S")

Tester = Callable[[str], tuple[bool, str]]
Fixer = Callable[[str, str], tuple[object, bool, Path]]


def last_run_output(log: str) -> str:
    runs = list(RUN_MARKER.finditer(log))
    builds = list(BUILD_MARKER.finditer(log))
    if runs and (not builds or builds[-1].start() < runs[-1].start()):
        return log[runs[-1].end() :]
    return log[-REPORT_CHARS:]


def failure_lines(output: str) -> list[str]:
    seen: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if SUMMARY_LINE.match(line) and line not in seen:
            seen.append(line)
    return seen


def failure_report(output: str, max_chars: int = REPORT_CHARS) -> str:
    errors = Counter(
        line.strip() for line in output.splitlines() if ERROR_LINE.match(line)
    )
    parts: list[str] = []
    if errors:
        parts.append("Most common error lines (count, line):")
        parts += [f"{count}x {line[:200]}" for line, count in errors.most_common(15)]
    lines = failure_lines(output)
    if lines:
        parts.append(f"\nFailing tests ({len(lines)}), first 40:")
        parts += [line[:200] for line in lines[:40]]
    parts.append("\nEnd of the test output:")
    parts += output.strip().splitlines()[-15:]
    return "\n".join(parts)[:max_chars]


def fix_task(report: str, extras: list[str]) -> str:
    text = (
        "This folder holds an existing app whose automated tests fail when run in "
        "an offline Docker container. Read PRD.md and constraints.md first.\n"
        "Fix the application so the tests pass. Many errors share one root "
        "cause, so find that first.\n"
        "Fix the app code, not the tests. Edit a test only if it clearly "
        "contradicts the PRD, and never delete tests or weaken assertions to "
        "make them pass.\n"
        "The test environment sets SECRET_KEY, ENVIRONMENT and DATABASE_URL "
        "(a fake value) and has no network.\n"
        "Only create and edit files. Do not run any commands, do not install "
        "packages and do not use the network. Do not change anything unrelated "
        "to the failures. Never hardcode secrets.\n"
        "Record each change and its reason in CHANGES.md.\n"
    )
    if extras:
        text += (
            "\nThese packages were missing from pyproject.toml and must be "
            "declared there: " + ", ".join(extras) + "\n"
        )
    return text + "\nTest failure report:\n\n" + report + "\n"


def read_extras(base: Path) -> list[str]:
    path = base / "test-result.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text()).get("auto_added_requirements", []))


def repair_until_green(
    run_id: str,
    tester: Tester,
    fixer: Fixer,
    runs_dir: Path = Path("runs"),
    max_rounds: int = MAX_ROUNDS,
    say: Callable[[str], None] = print,
) -> bool:
    base = st.run_dir(run_id, runs_dir)
    previous: list[str] | None = None
    for attempt in range(max_rounds + 1):
        say(f"Running the tests, attempt {attempt + 1} ...")
        ok, _ = tester(run_id)
        if ok:
            say("Tests passed")
            return True
        output = last_run_output((base / "test.log").read_text())
        signature = failure_lines(output)
        say(f"Tests failed: {len(signature)} failing or erroring tests")
        if previous is not None and signature == previous:
            say("No progress since the last fix. Stopping.")
            return False
        previous = signature
        if attempt == max_rounds:
            break
        say("Asking the fixer ...")
        message = fix_task(failure_report(output), read_extras(base))
        _, fixed, _ = fixer(run_id, message)
        if not fixed:
            say("The fixer failed. See fix.log in the run folder.")
            return False
    say("Stopping after the maximum number of fix rounds.")
    return False
