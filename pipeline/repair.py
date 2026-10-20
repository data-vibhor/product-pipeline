from collections.abc import Callable

from pipeline.llm import LLM
from pipeline.textutil import clean_text


def generate_checked(
    llm: LLM,
    system: str,
    user: str,
    checker: Callable[[str], list[str]],
    max_repairs: int = 2,
) -> tuple[str, list[str]]:
    text = clean_text(llm.chat(system, user))
    issues = checker(text)
    repairs = 0
    while issues and repairs < max_repairs:
        fix = (
            user
            + "\n\nYour previous draft:\n\n"
            + text
            + "\n\nIt failed these automatic checks:\n- "
            + "\n- ".join(issues)
            + "\n\nRewrite the full document so it passes every check. "
            "Keep the same headings and the same content priorities. "
            "If it is too long, cut to about 15 percent below the limit by "
            "shortening sentences and dropping low-value detail, never by "
            "removing headings. Return only the document."
        )
        text = clean_text(llm.chat(system, fix))
        issues = checker(text)
        repairs += 1
    return text.strip(), issues
