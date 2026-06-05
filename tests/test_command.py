from fastapi.testclient import TestClient

from maybot_control_center.app import app
from maybot_control_center import command

client = TestClient(app)


def test_snapshot_shape():
    s = command.snapshot()
    assert set(s) >= {"greeting_name", "monthly_goal", "account_base", "opportunities", "events"}
    assert isinstance(s["opportunities"], list) and isinstance(s["events"], list)


def test_demo_opportunities(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEMO", "1")
    tickers = {o["ticker"] for o in command.opportunities()}
    assert {"META", "AMD", "NVDA"} <= tickers
    for o in command.opportunities():
        assert o["status"] in {"EXECUTE", "READY", "WATCHING"}


def test_opportunities_from_env(monkeypatch):
    monkeypatch.delenv("MAYBOT_DEMO", raising=False)
    monkeypatch.setenv("MAYBOT_OPPORTUNITIES", '[{"ticker":"X","edge":1.0,"confidence":50,"status":"READY"}]')
    assert command.opportunities()[0]["ticker"] == "X"


def test_events_assembled(monkeypatch):
    monkeypatch.setattr("maybot_control_center.autopilot.status",
                        lambda: {"log": [{"kind": "fix", "title": "Fixing api", "message": "restart", "ts": 200}]})
    monkeypatch.setattr("maybot_control_center.comms.get_feed", lambda n: [{"from": "Nova", "content": "analysis done", "ts": 100}])
    ev = command.events()
    assert ev and ev[0]["ts"] == 200            # newest first
    assert any("Fixing api" in e["text"] for e in ev)


def test_command_endpoint():
    r = client.get("/api/command")
    assert r.status_code == 200 and "opportunities" in r.json()


def test_command_home_served():
    r = client.get("/")
    assert r.status_code == 200 and "Command Hall" in r.text
    assert client.get("/classic").status_code == 200
    assert client.get("/command.css").status_code == 200
    assert client.get("/vendor/three.module.js").status_code == 200


def test_immersive_scenes_served():
    # Realm Map (3D empire) + Disciple Command Chamber scenes and their assets.
    rm = client.get("/realm-map")
    assert rm.status_code == 200 and "Realm Map" in rm.text
    ch = client.get("/chamber")
    assert ch.status_code == 200 and "Command Chamber" in ch.text
    tc = client.get("/trade")
    assert tc.status_code == 200 and "Trade Center" in tc.text
    tr = client.get("/treasury")
    assert tr.status_code == 200 and "Treasury" in tr.text
    for path in ("/map.js", "/chamber.js", "/trade.js", "/treasury.js", "/lib.js", "/vendor/OrbitControls.js"):
        resp = client.get(path)
        assert resp.status_code == 200, path
        assert "javascript" in resp.headers["content-type"]


def test_sect_sprite_assets():
    # Realm Map sprite manifest merges baked fallbacks + authored overrides.
    man = client.get("/api/sect/manifest")
    assert man.status_code == 200
    data = man.json()
    assert "grand_pagoda" in data["sprites"] and "fountain" in data["sprites"]
    gp = data["sprites"]["grand_pagoda"]
    assert gp["source"] == "baked" and gp["url"].endswith("/baked/grand_pagoda.png")
    assert "anchorFx" in gp and "footTiles" in gp and "scale" in gp and "z" in gp
    png = client.get(gp["url"])
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    # art-pipeline hooks for authored scenery + per-hall landmarks (empty until art is dropped in)
    assert "scenery" in data and isinstance(data["scenery"], dict)
    assert "halls" in data and isinstance(data["halls"], dict)


def test_command_positions_and_bots(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEMO", "1")
    s = command.snapshot()
    assert s["positions"] and {"ticker", "side", "qty", "pnl"} <= set(s["positions"][0])
    assert s["bots"] and {"name", "pnl_today", "win_rate"} <= set(s["bots"][0])
