"""Stage: run the generated app in a headless browser inside Docker and crawl it.

Unit tests only prove the code runs. This stage proves a person can use the app:
no JavaScript errors, no failed requests and no dead buttons.
"""

import json
import re
import shutil
from pathlib import Path

from pipeline import state as st
from pipeline.testrun import (
    BUILD_TIMEOUT,
    IGNORED,
    INSTALL_SCRIPT,
    MAX_DEP_ROUNDS,
    Runner,
    docker_runner,
    missing_requirements,
)

BROWSER_TIMEOUT = 420
CRAWLER = Path(__file__).with_name("browsercrawl.py")
SECRET_NAME = re.compile(r"SECRET|KEY|TOKEN|PASSWORD", re.IGNORECASE)

DOCKERFILE = """FROM python:3.12-slim
WORKDIR /app
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright PYTHONDONTWRITEBYTECODE=1
COPY pyproject.toml _install_deps.py _extra_requirements.txt /app/
RUN python /app/_install_deps.py \\
    && pip install --no-cache-dir playwright aiosqlite \\
    && playwright install --with-deps chromium \\
    && chmod -R a+rX /ms-playwright
COPY . /app
RUN useradd -m tester && chown -R tester /app
USER tester
CMD ["sh", "/app/_browser_run.sh"]
"""

RUN_SCRIPT = """#!/bin/sh
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/app.log 2>&1 &
up=0
for i in $(seq 1 45); do
  if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" 2>/dev/null; then
    up=1; break
  fi
  sleep 1
done
if [ "$up" = "0" ]; then
  echo "FAILED app_did_not_start: the app never answered on /health"
  tail -n 40 /tmp/app.log
  exit 2
fi
python /app/_browsercrawl.py http://127.0.0.1:8000 --out /tmp/browser-report.json
code=$?
if [ "$code" != "0" ]; then
  echo "--- app log (last lines) ---"
  tail -n 30 /tmp/app.log
fi
exit $code
"""


def env_from_example(build: Path) -> dict[str, str]:
    """Dummy values for every variable in .env.example, so the app can start with no real services."""
    env: dict[str, str] = {}
    example = build / ".env.example"
    if example.exists():
        for line in example.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if SECRET_NAME.search(key):
                value = "x" * 40
            elif not value or value.lower().startswith(("your", "change", "<")):
                value = "dummy"
            env[key] = value
    env.update(
        {
            "DATABASE_URL": "sqlite+aiosqlite:////tmp/browser.db",
            "APP_ENV": "development",
            "ENVIRONMENT": "development",
        }
    )
    return env


def browser_passed(base: Path) -> bool:
    path = base / "browser-result.json"
    return path.exists() and json.loads(path.read_text()).get("status") == "passed"


def run_browser_check(
    run_id: str,
    runner: Runner = docker_runner,
    runs_dir: Path = Path("runs"),
) -> tuple[bool, str]:
    base = st.run_dir(run_id, runs_dir)
    build = base / "build"
    if not build.exists():
        raise ValueError("There is no build to check")
    if not (build / "pyproject.toml").exists():
        raise ValueError("The build has no pyproject.toml, so its dependencies cannot be installed")
    tag = f"pipeline-browser-{run_id}".lower()
    ctx = base / "browser-context"
    env = env_from_example(build)
    extras: list[str] = []
    log, status, ok, code, tail, rounds = "", "failed", False, 1, "", 0
    for rounds in range(1, MAX_DEP_ROUNDS + 1):
        if ctx.exists():
            shutil.rmtree(ctx)
        shutil.copytree(build, ctx, ignore=IGNORED)
        (ctx / "Dockerfile").write_text(DOCKERFILE)
        (ctx / "_install_deps.py").write_text(INSTALL_SCRIPT)
        (ctx / "_extra_requirements.txt").write_text("\n".join(extras) + "\n")
        (ctx / "_browser_run.sh").write_text(RUN_SCRIPT)
        shutil.copy(CRAWLER, ctx / "_browsercrawl.py")
        code, build_out = runner(["docker", "build", "-t", tag, str(ctx)], BUILD_TIMEOUT)
        log += f"\n=== round {rounds}: docker build ===\n" + build_out
        if code != 0:
            status, ok, tail = "build_failed", False, build_out
            break
        env_flags: list[str] = []
        for key, value in env.items():
            env_flags += ["-e", f"{key}={value}"]
        run_cmd = [
            "docker", "run", "--rm", "--network", "none",
            "--memory", "1500m", "--cpus", "2", "--pids-limit", "512", "--shm-size", "512m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            *env_flags, tag,
        ]
        code, out = runner(run_cmd, BROWSER_TIMEOUT)
        log += f"\n=== round {rounds}: browser run (network off) ===\n" + out
        ok = code == 0
        status, tail = ("passed" if ok else "failed"), out
        if ok:
            break
        new = [spec for spec in missing_requirements(out) if spec not in extras]
        if not new:
            break
        extras += new
    (base / "browser.log").write_text(log)
    (base / "browser-result.json").write_text(
        json.dumps({"status": status, "exit_code": code, "rounds": rounds, "auto_added_requirements": extras}) + "\n"
    )
    return ok, "\n".join(tail.strip().splitlines()[-25:])
