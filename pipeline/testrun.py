import json
import re
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
MAX_DEP_ROUNDS = 6
HARNESS_EXTRAS = ["pytest", "pytest-asyncio", "httpx"]
TEST_ENV = {
    "SECRET_KEY": "test-only-secret-not-for-production",  # nosec B105
    "ENVIRONMENT": "development",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
}
LOCAL_MODULES = {"app", "tests", "migrations", "conftest"}
MODULE_TO_PACKAGE = {
    "jose": "python-jose[cryptography]",
    "multipart": "python-multipart",
    "dotenv": "python-dotenv",
    "jwt": "pyjwt",
    "email_validator": "email-validator",
    "yaml": "pyyaml",
    "PIL": "pillow",
    "bcrypt": "bcrypt<5",
}
NO_MODULE = re.compile(r"No module named '([A-Za-z0-9_\.]+)'")
PIP_HINT = re.compile(
    r"pip install ['\"]?([A-Za-z0-9][A-Za-z0-9_\-\.]*(?:\[[A-Za-z0-9_,\-]+\])?)"
)

DOCKERFILE = """FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml _install_deps.py _extra_requirements.txt /app/
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
from pathlib import Path

with open("pyproject.toml", "rb") as handle:
    data = tomllib.load(handle)
project = data.get("project", {})
deps = list(project.get("dependencies", []))
for group in project.get("optional-dependencies", {}).values():
    deps.extend(group)
for group in data.get("dependency-groups", {}).values():
    deps.extend(item for item in group if isinstance(item, str))
extra = [
    line.strip()
    for line in Path("_extra_requirements.txt").read_text().splitlines()
    if line.strip()
]
base = ["pytest", "pytest-asyncio", "httpx"]
subprocess.check_call(
    [sys.executable, "-m", "pip", "install", "--no-cache-dir", *base, *deps, *extra]
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


def missing_requirements(output: str) -> list[str]:
    found: list[str] = []
    for match in PIP_HINT.finditer(output):
        spec = match.group(1)
        if spec not in found:
            found.append(spec)
    for match in NO_MODULE.finditer(output):
        top = match.group(1).split(".")[0]
        if top in LOCAL_MODULES:
            continue
        spec = MODULE_TO_PACKAGE.get(top, top)
        if spec not in found:
            found.append(spec)
    return found


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
    tag = f"pipeline-test-{run_id}".lower()
    ctx = base / "test-context"
    extras: list[str] = []
    log = ""
    status, ok, code, tail, rounds = "failed", False, 1, "", 0
    for rounds in range(1, MAX_DEP_ROUNDS + 1):
        if ctx.exists():
            shutil.rmtree(ctx)
        shutil.copytree(build, ctx, ignore=IGNORED)
        (ctx / "Dockerfile").write_text(DOCKERFILE)
        (ctx / "_install_deps.py").write_text(INSTALL_SCRIPT)
        (ctx / "_extra_requirements.txt").write_text("\n".join(extras) + "\n")
        code, build_out = runner(["docker", "build", "-t", tag, str(ctx)], BUILD_TIMEOUT)
        log += f"\n=== round {rounds}: docker build ===\n" + build_out
        if code != 0:
            status, ok, tail = "build_failed", False, build_out
            break
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
        log += f"\n=== round {rounds}: docker run (network off) ===\n" + test_out
        ok = code == 0
        status, tail = ("passed" if ok else "failed"), test_out
        if ok:
            break
        new = [spec for spec in missing_requirements(test_out) if spec not in extras]
        if not new:
            break
        extras += new
    (base / "test.log").write_text(log)
    result = {
        "status": status,
        "exit_code": code,
        "rounds": rounds,
        "harness_extras": HARNESS_EXTRAS,
        "auto_added_requirements": extras,
        "test_env_keys": list(TEST_ENV),
    }
    (base / "test-result.json").write_text(json.dumps(result) + "\n")
    lines = tail.strip().splitlines()[-15:]
    if extras:
        (base / "suggested-dependencies.txt").write_text("\n".join(extras) + "\n")
        lines.append(
            "Auto-added requirements (missing from the build's pyproject.toml): "
            + ", ".join(extras)
        )
    return ok, "\n".join(lines)
