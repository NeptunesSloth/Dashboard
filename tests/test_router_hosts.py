"""Host management routes are served by routers/hosts.py after the split."""
from starlette.testclient import TestClient

from maybot_control_center import app, deps


client = TestClient(app.app)


def test_host_routes_mounted_via_router():
    paths = {r.path for r in app.app.routes}
    for p in ("/api/hosts", "/api/hosts/gen-token", "/api/hosts/enroll-token",
              "/api/hosts/test", "/api/hosts/{name}/projects", "/api/hosts/{name}/discover",
              "/api/hosts/{name}/update", "/api/hosts/{name}", "/api/fleet/update"):
        assert p in paths
    # settings routes stayed in app.py (were interleaved with hosts)
    assert "/api/settings" in paths
    # served live through the router
    r = client.get("/api/hosts")
    assert r.status_code == 200 and isinstance(r.json().get("hosts"), list)


def test_mask_token_shared_in_deps():
    # _mask_token is used by both the hosts router and app.py's accounts panel.
    assert app._mask_token is deps.mask_token
    assert deps.mask_token("abcdefghij").startswith("abc")
    assert deps.mask_token("xyz") == "•••"
