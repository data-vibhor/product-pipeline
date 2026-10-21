from pipeline.build import child_env


def test_child_env_sets_pwd_to_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("PWD", "/somewhere/else")
    assert child_env(tmp_path)["PWD"] == str(tmp_path)
