import re

HEADINGS = [
    "Problem",
    "Target user",
    "Proposed solution",
    "MVP scope",
    "Non-goals",
    "Existing alternatives",
    "Risks",
    "Assumptions to validate",
    "Cheapest validation test",
    "Recommendation",
]
PRD_HEADINGS = [
    "Overview",
    "Goals",
    "Non-goals",
    "Users and use cases",
    "Functional requirements",
    "Acceptance criteria",
    "Data and privacy",
    "Technical approach",
    "Risks and open questions",
    "Milestones",
]
MAX_WORDS = 550
MAX_PRD_WORDS = 1300
MAX_MVP_BULLETS = 5
MIN_ACCEPTANCE_CRITERIA = 5


def _heading_issues(text: str, expected: list[str]) -> list[str]:
    found = re.findall(r"^## (.+?)\s*$", text, flags=re.MULTILINE)
    if found == expected:
        return []
    missing = [h for h in expected if h not in found]
    if missing:
        return ["missing headings: " + ", ".join(missing)]
    return ["headings are out of order or duplicated"]


def _style_issues(text: str, max_words: int) -> list[str]:
    issues: list[str] = []
    words = len(text.split())
    if words > max_words:
        issues.append(f"too long: {words} words (max {max_words})")
    if "\u2014" in text:
        issues.append("contains an em dash")
    if " \u2013 " in text:
        issues.append("contains a spaced en dash used as a dash")
    return issues


def _section(text: str, name: str) -> str | None:
    pattern = rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    return match.group(1) if match else None


def _items(section: str) -> list[str]:
    return [
        line
        for line in section.splitlines()
        if re.match(r"\s*([-*]|\d+[.)])\s", line)
    ]


def check_brief(text: str) -> list[str]:
    issues = _heading_issues(text, HEADINGS)
    issues += _style_issues(text, MAX_WORDS)
    section = _section(text, "MVP scope")
    if section is not None:
        count = len(_items(section))
        if count > MAX_MVP_BULLETS:
            issues.append(f"MVP scope has {count} bullets (max {MAX_MVP_BULLETS})")
    return issues


def check_prd(text: str) -> list[str]:
    issues = _heading_issues(text, PRD_HEADINGS)
    issues += _style_issues(text, MAX_PRD_WORDS)
    section = _section(text, "Acceptance criteria")
    if section is not None:
        count = len(_items(section))
        if count < MIN_ACCEPTANCE_CRITERIA:
            issues.append(
                f"only {count} acceptance criteria (min {MIN_ACCEPTANCE_CRITERIA})"
            )
    return issues
