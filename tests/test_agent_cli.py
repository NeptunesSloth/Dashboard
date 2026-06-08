"""`python -m maybot_agent` helper CLI (doctor / list-bots / add-bot)."""
from maybot_agent import __main__ as cli
from maybot_agent import config


def test_add_then_list_bots(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "PROJECTS_FILE", tmp_path / "projects.yaml")

    assert cli.main(["add-bot", "--name", "alpha", "--type", "generic", "--path", "/srv/alpha"]) == 0
    assert (tmp_path / "projects.yaml").exists()
    assert "alpha" in capsys.readouterr().out

    assert cli.main(["list-bots"]) == 0
    out = capsys.readouterr().out
    assert "alpha" in out and "generic" in out

    # Duplicate names are rejected (non-zero exit).
    assert cli.main(["add-bot", "--name", "alpha", "--type", "generic"]) == 1


def test_doctor_runs_without_network(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(config, "PROJECTS_FILE", tmp_path / "p.yaml")
    monkeypatch.delenv("MAYBOT_CONTROL_CENTER_URL", raising=False)
    monkeypatch.setenv("MAYBOT_API_TOKEN", "a-token")

    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out.lower()
    assert "doctor" in out and "projects file" in out
    assert "a-token" not in out          # never print the secret verbatim
