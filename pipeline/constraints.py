from pathlib import Path

CONSTRAINTS_FILE = Path("constraints.md")


def with_constraints(system: str, constraints_file: Path = CONSTRAINTS_FILE) -> str:
    if not constraints_file.exists():
        return system
    return (
        system.rstrip()
        + "\n\nFounder constraints. Respect these in everything you write:\n\n"
        + constraints_file.read_text().strip()
        + "\n"
    )
