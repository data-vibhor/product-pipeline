import json
import re
import tomllib
from pathlib import Path

from pipeline import state as st

KIT_DIR = Path(__file__).parent / "deploy_kit"
KIT_FILES = {
    "Dockerfile.prod.tmpl": "Dockerfile.prod",
    "start.py.tmpl": "start.py",
    "dockerignore.tmpl": ".dockerignore",
    "render.yaml.tmpl": "render.yaml",
    "ci.yml.tmpl": ".github/workflows/ci.yml",
}


def service_name(build_dir: Path) -> str:
    data = tomllib.loads((build_dir / "pyproject.toml").read_text())
    name = str(data.get("project", {}).get("name", "app"))
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return slug or "app"


def tests_passed(base: Path) -> bool:
    path = base / "test-result.json"
    if not path.exists():
        return False
    return json.loads(path.read_text()).get("status") == "passed"


def browser_check_passed(base: Path) -> bool:
    path = base / "browser-result.json"
    return path.exists() and json.loads(path.read_text()).get("status") == "passed"


def write_kit(run_id: str, runs_dir: Path = Path("runs"), require_browser: bool = False) -> list[str]:
    base = st.run_dir(run_id, runs_dir)
    build = base / "build"
    if not build.exists():
        raise ValueError("There is no build to deploy")
    if not tests_passed(base):
        raise ValueError("The tests have not passed yet. Run test-fix first")
    if require_browser and not browser_check_passed(base):
        raise ValueError(
            "The browser check has not passed. Run browser-test first, or use deploy-kit --skip-browser"
        )
    for needed in ("pyproject.toml", "app/main.py"):
        if not (build / needed).exists():
            raise ValueError(f"The build has no {needed}")
    main = (build / "app" / "main.py").read_text()
    if '"/health"' not in main and "'/health'" not in main:
        raise ValueError("The app has no /health route. Add one before deploying")
    name = service_name(build)
    written: list[str] = []
    for source, dest in KIT_FILES.items():
        text = (KIT_DIR / source).read_text().replace("{{SERVICE_NAME}}", name)
        text = text.replace("{{COPY_STATIC}}", "COPY static/ ./static/\n" if (build / "static").is_dir() else "")
        target = build / dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        written.append(dest)
    return written
