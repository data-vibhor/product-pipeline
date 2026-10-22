import json
from pathlib import Path

import pytest

from pipeline import state as st
from pipeline.deploy import KIT_DIR, KIT_FILES, service_name, write_kit


def make(tmp_path: Path, passed: bool = True, health: bool = True):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    base = st.run_dir(run.run_id, runs)
    build = base / "build"
    (build / "app").mkdir(parents=True)
    (build / "pyproject.toml").write_text('[project]\nname = "Credit Invoice_Tracker"\n')
    route = '@app.get("/health")\n' if health else ""
    (build / "app" / "main.py").write_text(route + "x = 1\n")
    status = "passed" if passed else "failed"
    (base / "test-result.json").write_text(json.dumps({"status": status}))
    return runs, run.run_id, build


def test_writes_every_kit_file_with_the_service_name(tmp_path):
    runs, run_id, build = make(tmp_path)
    written = write_kit(run_id, runs)
    assert sorted(written) == sorted(KIT_FILES.values())
    for name in written:
        assert (build / name).exists()
    assert "name: credit-invoice-tracker" in (build / "render.yaml").read_text()
    assert "{{" not in (build / "render.yaml").read_text()
    assert "region: singapore" in (build / "render.yaml").read_text()


def test_refuses_when_tests_have_not_passed(tmp_path):
    runs, run_id, _ = make(tmp_path, passed=False)
    with pytest.raises(ValueError, match="tests have not passed"):
        write_kit(run_id, runs)


def test_refuses_when_there_is_no_health_route(tmp_path):
    runs, run_id, _ = make(tmp_path, health=False)
    with pytest.raises(ValueError, match="/health"):
        write_kit(run_id, runs)


def test_refuses_without_a_build(tmp_path):
    runs = tmp_path / "runs"
    run = st.new_run("idea", runs)
    with pytest.raises(ValueError, match="no build"):
        write_kit(run.run_id, runs)


def test_service_name_is_a_safe_slug(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "Weird__Name!"\n')
    assert service_name(tmp_path) == "weird-name"


def load_start() -> dict:
    source = (KIT_DIR / "start.py.tmpl").read_text()
    namespace: dict = {"__name__": "kit_start"}
    exec(compile(source, "start.py", "exec"), namespace)  # noqa: S102  # nosec B102
    return namespace


def test_database_url_is_made_asyncpg_friendly():
    fix = load_start()["normalize_database_url"]
    neon = "postgresql://u:p@h.neon.tech/db?sslmode=require&channel_binding=require"
    assert fix(neon) == "postgresql+asyncpg://u:p@h.neon.tech/db?ssl=require"
    assert fix("postgres://u:p@h/db") == "postgresql+asyncpg://u:p@h/db"
    assert fix("sqlite+aiosqlite:///x.db") == "sqlite+aiosqlite:///x.db"
    done = "postgresql+asyncpg://u:p@h/db?ssl=require"
    assert fix(done) == done
