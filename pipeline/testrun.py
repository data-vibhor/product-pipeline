import json
import shutil
import subprocess  # nosec B404
from collections.abc import Callable
from pathlib import Path

from pipeline import state as st

IGNORED = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".git", ".env", "test.db", ".pytest_cache"
)
BUILD_TIMEOUT = 900
TEST_TIMEOUT = 300
HARNESS_EXTRAS = ["pytest", "pytest-asyncio", "httpx"]
TEST_ENV = {
    "SECRET_KEY": "test-only-secret-not-for-production",  # nosec B105 - throwaway value for an offline test container
    "ENVIRONMENT": "development",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
}

DOCKERFILE = """FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml _install_deps.py /app/
RUN python /app/_install_deps.py
COPY . /app
RUN useradd -m tester && chown -R tester /app
USER tester
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
"""

INSTALL_SCRIPT = """import subprocess
import sys
import tomllib

with open("pyproject.toml", "rb") as handle:
    data = tomllib.load(handle)
project = data.get("project", {})
deps = list(project.get("dependencies", []))
for group in project.get("optional-dependencies", {}).values():
    deps.extend(group)
for group in data.get("dependency-groups", {}).values():
    deps.extend(item for item in group if isinstance(item, str))
base = ["pytest", "pytest-asyncio", "httpx"]
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "--no-cache-dir", *base, *deps]
)
"""

Runner = Callable[[list[str], int], tuple[int, str]]


def docker_runner(cmd: list[str], timeout: int) -> tuple[int, str]:
    if shutil.which(cmd[0]) is None:
        raise RuntimeError("docker was not found. Start Colima and try again")
    try:
        proc = subprocess.run(  # nosec B603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, f"Timed out after {timeout} seconds"
    return proc.returncode, proc.stdout + proc.stderr


def run_tests(
    run_id: str,
    runner: Runner = docker_runner,
    runs_dir: Path = Path("runs"),
) -> tuple[bool, str]:
    base = st.run_dir(run_id, runs_dir)
    build = base / "build"
    if not build.exists():
        raise ValueError("There is no build to test")
    if not (build / "pyproject.toml").exists():
        raise ValueError("The build has no pyproject.toml, so its dependencies cannot be installed")
    ctx = base / "test-context"
    if ctx.exists():
        shutil.rmtree(ctx)
    shutil.copytree(build, ctx, ignore=IGNORED)
    (ctx / "Dockerfile").write_text(DOCKERFILE)
    (ctx / "_install_deps.py").write_text(INSTALL_SCRIPT)
    tag = f"pipeline-test-{run_id}".lower()
    code, build_out = runner(["docker", "build", "-t", tag, str(ctx)], BUILD_TIMEOUT)
    log = "=== docker build ===\n" + build_out
    if code != 0:
        status, ok, tail = "build_failed", False, build_out
    else:
        env_flags: list[str] = []
        for key, value in TEST_ENV.items():
            env_flags += ["-e", f"{key}={value}"]
        run_cmd = [
            "docker", "run", "--rm", "--network", "none",
            "--memory", "1g", "--cpus", "1", "--pids-limit", "256",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            *env_flags, tag,
        ]
        code, test_out = runner(run_cmd, TEST_TIMEOUT)
        log += "\n=== docker run (network off) ===\n" + test_out
        ok = code == 0
        status, tail = ("passed" if ok else "failed"), test_out
    (base / "test.log").write_text(log)
    result = {
        "status": status,
        "exit_code": code,
        "harness_extras": HARNESS_EXTRAS,
        "test_env_keys": list(TEST_ENV),
    }
    (base / "test-result.json").write_text(json.dumps(result) + "\n")
    return ok, "\n".join(tail.strip().splitlines()[-15:])
