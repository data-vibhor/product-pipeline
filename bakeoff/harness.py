"""Bake-off: ask a model to write tests for an app, then count the seeded bugs they catch."""

import json
import os
import shutil
import subprocess  # nosec B404
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from bakeoff.mutations import MUTATIONS
from pipeline.build import child_env

COPY_IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".git", "*.db", "*.db-*", ".pytest_cache"
)
TEST_ENV = {
    "SECRET_KEY": "test-secret-key-for-testing-min-32-chars",  # nosec B105
    "ENVIRONMENT": "testing",
}
PYTEST_TIMEOUT = 300
MODEL_TIMEOUT = 1200

Mutation = tuple[str, str, str, str]
Runner = Callable[[list[str], Path, int], tuple[int, str]]
ModelRunner = Callable[[str, str, Path], tuple[int, str]]


def pytest_runner(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(  # nosec B603
            cmd,
            cwd=cwd,
            env={**os.environ, **TEST_ENV},
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, f"Timed out after {timeout} seconds"
    return proc.returncode, proc.stdout + proc.stderr


def opencode_model_runner(model: str, message: str, cwd: Path) -> tuple[int, str]:
    exe = shutil.which("opencode")
    if exe is None:
        raise RuntimeError("opencode was not found on PATH")
    try:
        proc = subprocess.run(  # nosec B603
            [exe, "run", "--model", model, message],
            cwd=cwd,
            env=child_env(cwd),
            capture_output=True,
            text=True,
            timeout=MODEL_TIMEOUT,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return 124, f"OpenCode timed out after {MODEL_TIMEOUT} seconds"
    return proc.returncode, proc.stdout + proc.stderr


@dataclass
class Score:
    clean_passed: bool
    clean_output: str = ""
    results: list[tuple[str, str]] = field(default_factory=list)

    @property
    def killed(self) -> int:
        return sum(1 for _, status in self.results if status == "KILLED")

    @property
    def total(self) -> int:
        return sum(1 for _, status in self.results if status != "BAD PATCH")

    def summary(self) -> str:
        if not self.clean_passed:
            return "INVALID: the tests fail on the unmodified app"
        return f"killed {self.killed} of {self.total}"


def pytest_cmd(python: str) -> list[str]:
    return [python, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"]


def score_suite(
    app_dir: Path,
    python: str,
    workdir: Path,
    mutations: list[Mutation] = MUTATIONS,
    runner: Runner = pytest_runner,
    workers: int = 4,
) -> Score:
    cmd = pytest_cmd(python)
    clean = workdir / "clean"
    shutil.rmtree(clean, ignore_errors=True)
    shutil.copytree(app_dir, clean, ignore=COPY_IGNORE)
    code, output = runner(cmd, clean, PYTEST_TIMEOUT)
    if code != 0:
        return Score(False, output[-3000:])

    def one(item: tuple[int, Mutation]) -> tuple[str, str]:
        number, (name, file, old, new) = item
        target = workdir / f"m{number:02d}"
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(app_dir, target, ignore=COPY_IGNORE)
        path = target / file
        text = path.read_text() if path.exists() else ""
        if text.count(old) != 1:
            shutil.rmtree(target, ignore_errors=True)
            return name, "BAD PATCH"
        path.write_text(text.replace(old, new))
        rc, _ = runner(cmd, target, PYTEST_TIMEOUT)
        shutil.rmtree(target, ignore_errors=True)
        return name, "KILLED" if rc != 0 else "SURVIVED"

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(one, enumerate(mutations, start=1)))
    return Score(True, results=results)


def candidate_message(prd: str) -> str:
    return (
        "You are a test engineer. The app in this folder implements the PRD below.\n"
        "Write an independent pytest suite in the tests/ folder, including any "
        "conftest.py it needs. Create files only inside tests/. Do not edit the app. "
        "Do not run commands, install packages or use the network.\n"
        "Tests must not need a running database or external service; use an "
        "in-memory database or fakes. ENVIRONMENT is 'testing' and SECRET_KEY is set.\n"
        "Cover every functional requirement, boundary values, error paths, "
        "authorization (one user must not reach another user's data), session and "
        "cookie security, CSRF protection and what the rendered pages show.\n\n"
        "PRD:\n\n" + prd
    )


def prepare_candidate(app_dir: Path, prd: str, workspace: Path) -> Path:
    shutil.rmtree(workspace, ignore_errors=True)
    shutil.copytree(
        app_dir,
        workspace,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".git", "*.db", "*.db-*", ".pytest_cache", "tests"
        ),
    )
    (workspace / "tests").mkdir()
    (workspace / "PRD.md").write_text(prd)
    return workspace


def run_candidate(
    model: str,
    app_dir: Path,
    python: str,
    root: Path,
    model_runner: ModelRunner = opencode_model_runner,
    runner: Runner = pytest_runner,
) -> dict:
    prd = (app_dir / "PRD.md").read_text()
    slug = model.replace("/", "_")
    workspace = prepare_candidate(app_dir, prd, root / slug / "work")
    code, log = model_runner(model, candidate_message(prd), workspace)
    (root / slug / "model.log").write_text(log)
    tests = [p for p in (workspace / "tests").rglob("test_*.py")]
    if not tests:
        result = {"model": model, "status": "no tests written", "exit": code}
    else:
        score = score_suite(workspace, python, root / slug / "mut", runner=runner)
        result = {
            "model": model,
            "status": score.summary(),
            "exit": code,
            "test_files": len(tests),
            "results": score.results,
        }
    (root / slug / "result.json").write_text(json.dumps(result, indent=2))
    return result
