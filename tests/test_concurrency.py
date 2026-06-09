import yaml
from concurrent.futures import ThreadPoolExecutor
from maybot_control_center import config, authz, agents


def test_atomic_write_no_corruption_under_concurrency(tmp_path):
    p = tmp_path / "devices.yaml"
    def w(i):
        config._atomic_write(p, yaml.safe_dump({"devices": [{"name": f"h{i}", "url": f"http://x/{i}"}]}))
    with ThreadPoolExecutor(max_workers=40) as ex:
        list(ex.map(w, range(400)))
    # the file must always be a complete, parseable YAML doc (never torn)
    data = yaml.safe_load(p.read_text())
    assert isinstance(data.get("devices"), list) and len(data["devices"]) == 1


def test_loaders_tolerate_corrupt_file(tmp_path, monkeypatch):
    bad = tmp_path / "devices.yaml"; bad.write_text("devices:\n  - name: a\n: : broken\n")
    monkeypatch.setattr(config, "DEVICES_FILE", bad)
    assert config.load_devices() == []                       # no exception, empty
    ub = tmp_path / "users.yaml"; ub.write_text("users: [\n")
    monkeypatch.setattr(authz, "USERS_FILE", ub)
    assert authz.load_users() == []
    ab = tmp_path / "agents.yaml"; ab.write_text("agents: {oops\n")
    monkeypatch.setattr(agents, "AGENTS_FILE", ab)
    assert agents.file_agents() == [] and agents.load_agents() == []
