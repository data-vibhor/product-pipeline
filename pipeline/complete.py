"""Finish a build that stopped early (for example on the time limit), one piece at a time."""

from collections.abc import Callable
from pathlib import Path

from pipeline.fix import apply_fix

READ_FIRST = (
    "Read PRD.md, constraints.md, app/main.py and every file in app/routes first. "
    "The backend already exists. Do not change its routes or behaviour. "
    "Only create and edit files. Do not run any commands, do not install packages "
    "and do not use the network.\n\n"
)

TASKS: dict[str, str] = {
    "frontend": READ_FIRST
    + "Build the missing mobile-first frontend exactly as UX.md describes, as plain "
    "HTML, CSS and vanilla JavaScript in a static/ folder. Read UX.md before writing code. Check that app/main.py serves static/index.html "
    "and the static files, and fix that wiring if it does not.\n"
    "Screens: signup with the consent checkbox and privacy notice, login, invoice "
    "list, upload (camera capture and file pick, canvas down-scale before upload), "
    "review and edit with low-confidence fields flagged, reminder links, paste a "
    "reply or upload a screenshot, CSV import, account deletion.\n"
    "Every state-changing request must send the CSRF token the API expects. Never "
    "put user text into innerHTML; escape it. Include the PWA manifest icons "
    "reference and a service worker that never caches API responses.",
    "tests": READ_FIRST
    + "Write the pytest suite in tests/, including conftest.py, covering every "
    "acceptance criterion in PRD.md. Use an in-memory SQLite database through "
    "dependency overrides and fake the AI, storage and email providers. No network.\n"
    "Include tests that: one owner cannot read, change or delete another owner's "
    "data; state-changing requests without a CSRF token are rejected; the cron "
    "endpoints reject requests without the secret; the session cookie has the "
    "required flags; Indian amounts and dd/mm/yyyy dates parse as the PRD says; "
    "duplicate invoices are flagged; AI output never changes an invoice status.\n"
    "Also make pyproject.toml installable: every dependency must exist on PyPI and "
    "be used by the code. Remove unused ones such as python-csv, openpyxl and "
    "apscheduler, and add aiosqlite and pytest-asyncio for the tests. Pin bcrypt "
    "below 5 if passlib is used.",
    "docs": READ_FIRST
    + "Write README.md with run steps and environment variables, a complete "
    ".env.example with no real secrets, a .gitignore, and NOTES.md under "
    "'Decisions and open questions' listing every assumption you made.",
}

Fixer = Callable[[str, str], tuple[object, bool, Path]]


def complete_message(task: str) -> str:
    if task not in TASKS:
        raise ValueError(f"Unknown task '{task}'. Choose one of: {', '.join(TASKS)}")
    return TASKS[task]


def run_complete(run_id: str, task: str, fixer: Fixer | None = None):
    message = complete_message(task)
    use = fixer or (lambda rid, text: apply_fix(rid, text, keep_partial=True))
    return use(run_id, message)
