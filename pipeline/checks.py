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
MAX_WORDS = 450
MAX_MVP_BULLETS = 5


def check_brief(text: str) -> list[str]:
    issues: list[str] = []
    found = re.findall(r"^## (.+?)\s*$", text, flags=re.MULTILINE)
    if found != HEADINGS:
        missing = [h for h in HEADINGS if h not in found]
        if missing:
            issues.append("missing headings: " + ", ".join(missing))
        else:
            issues.append("headings are out of order or duplicated")
    words = len(text.split())
    if words > MAX_WORDS:
        issues.append(f"too long: {words} words (max {MAX_WORDS})")
    if "\u2014" in text:
        issues.append("contains an em dash")
    section = re.search(
        r"^## MVP scope\s*\n(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if section:
        bullets = [
            ln
            for ln in section.group(1).splitlines()
            if ln.strip().startswith(("-", "*"))
        ]
        if len(bullets) > MAX_MVP_BULLETS:
            issues.append(
                f"MVP scope has {len(bullets)} bullets (max {MAX_MVP_BULLETS})"
            )
    return issues
