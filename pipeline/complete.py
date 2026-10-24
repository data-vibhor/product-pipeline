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

FRONT = (
    "Read UX.md and API.md only, then write code. They are the whole contract. "
    "Do not read the backend. Do not change any backend file except where told. "
    "Plain HTML, CSS and vanilla JavaScript. Never put user text into innerHTML. "
    "Only create and edit files; do not run commands, install packages or use "
    "the network.\n\n"
)

TASKS: dict[str, str] = {
    "frontend-core": FRONT
    + "Create the app shell in static/: index.html, styles.css (mobile first, "
    "44 px touch targets, bottom navigation with Today, Invoices, Account), app.js "
    "(a small router, an api() helper that sends the CSRF header, an escape() "
    "helper), manifest wiring, sw.js (never cache API responses) and icons/ (simple "
    "generated PNG or SVG icons). Build the landing, signup (with the consent "
    "checkbox and privacy notice), login and Account screens. Check app/main.py "
    "serves static/index.html and static/ correctly and fix that wiring only.",
    "frontend-invoices": FRONT
    + "static/ already has the shell from the previous step. Add the Today screen "
    "(ready reminders, one Send reminder button each, then the 'Did you send it?' "
    "Yes or Skip step), the Invoices list with search, the Add invoice flow "
    "(camera or file pick, canvas down-scale to about 1 MB before upload, progress "
    "indicator, review cards with low-confidence fields highlighted and blocking "
    "save), the invoice detail with Mark paid and Delete, each with a confirm step.",
    "frontend-extras": FRONT
    + "static/ already has the shell, Today and invoice screens. Add the paste "
    "reply screen with the confirm card ('Promised on ... Correct?'), the CSV "
    "import screen with its result (imported, duplicates, errors), the empty, "
    "loading and error states for every screen, and the delete account confirm. "
    "Then re-read the UX.md rules and fix any screen that breaks them.",
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
    "tests-more": READ_FIRST
    + "tests/conftest.py and tests/test_auth.py already exist. Keep them and reuse "
    "their fixtures. Add these files, one at a time, each covering the PRD "
    "acceptance criteria for its area: tests/test_invoices.py (create, list, "
    "update, mark paid, delete, duplicates, CSV import), tests/test_isolation.py "
    "(owner A can never read, change or delete owner B's invoices or replies), "
    "tests/test_csrf.py (every state-changing endpoint rejects a missing or wrong "
    "token), tests/test_cron.py (a missing or wrong secret gets 403; reminders are "
    "created once), tests/test_parsing.py (Indian amounts and dd/mm/yyyy dates, "
    "ambiguous dates), tests/test_replies.py (a parsed reply never changes status "
    "until the owner confirms). Fake the AI, storage and email providers.",
    "hardening": READ_FIRST
    + "Fix these confirmed security defects. Each fix needs a test in "
    "tests/test_hardening.py that fails before the fix.\n"
    "1. static/utils/escape.js: escapeHtml and escapeAttr replace each character "
    "with itself, so nothing is escaped. Use the real entities (&amp; &lt; &gt; "
    "&quot; &#039;). Add a Python test that reads the file and checks the entity "
    "strings are present and that no replace() maps a character to itself.\n"
    "2. Every static/**/*.js template that goes into innerHTML must escape every "
    "value that comes from the API or the user, including the confirm messages in "
    "static/screens/invoices.js. Prefer textContent. Add a Python test that scans "
    "the JS and fails on any interpolation of customer_name, invoice_number, "
    "customer_phone, customer_email, notes or an error detail that is not wrapped "
    "in escapeHtml or escapeAttr.\n"
    "3. DELETE /auth/account must require the current password in the request body "
    "and must erase the owner's invoices, customers, replies and sessions, not "
    "only mark the user deleted. Update the frontend account screen to ask for "
    "the password.\n"
    "4. Replace outdated or unused dependencies: use bcrypt directly or passlib "
    "with bcrypt below 5; replace python-jose with PyJWT.",
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


def run_complete(
    run_id: str,
    task: str,
    fixer: Fixer | None = None,
    runs_dir: Path = Path("runs"),
):
    message = complete_message(task)
    use = fixer or (lambda rid, text: apply_fix(rid, text, keep_partial=True))
    result = use(run_id, message)
    log = runs_dir / run_id / "fix.log"
    if log.exists():
        (runs_dir / run_id / f"fix-{task}.log").write_text(log.read_text())
    return result
