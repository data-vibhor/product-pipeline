REPLACEMENTS = {
    "\u2010": "-",
    "\u2011": "-",
    "\u00a0": " ",
}


def clean_text(text: str) -> str:
    for bad, good in REPLACEMENTS.items():
        text = text.replace(bad, good)
    return text
