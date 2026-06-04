from maybot_control_center import pullrequest, artifacts, governance


def setup_function():
    artifacts.clear()


def test_proposes_artifact_by_default(monkeypatch):
    monkeypatch.setattr(pullrequest, "ENABLED", False)
    monkeypatch.setattr(pullrequest, "_plan",
                        lambda coder, project, cause: {"title": "Fix null order id", "body": "guard it", "diff": "--- a\n+++ b\n"})
    monkeypatch.setattr(governance, "leader", lambda: "Forge")
    res = pullrequest.propose("TradeBot", "prod-1", "null order id crash")
    assert res["opened"] is False and res["proposed"] is True and res["title"] == "Fix null order id"
    arts = artifacts.catalog()
    assert arts and arts[0]["name"].startswith("Proposed PR — TradeBot")
    assert "```diff" in arts[0]["content"]


def test_opens_real_pr_when_enabled(monkeypatch):
    monkeypatch.setattr(pullrequest, "ENABLED", True)
    monkeypatch.setattr(pullrequest, "_gh_available", lambda: True)
    monkeypatch.setattr(pullrequest, "_plan",
                        lambda c, p, cause: {"title": "Patch", "body": "b", "diff": "real diff"})
    monkeypatch.setattr(pullrequest, "_open_pr", lambda repo, t, b, d: "https://github.com/o/r/pull/7")
    res = pullrequest.propose("owner/repo", "github", "bug", coder="Forge")
    assert res["opened"] is True and res["url"].endswith("/pull/7")


def test_falls_back_to_proposal_when_no_repo(monkeypatch):
    monkeypatch.setattr(pullrequest, "ENABLED", True)
    monkeypatch.setattr(pullrequest, "_gh_available", lambda: True)
    monkeypatch.setattr(pullrequest, "DEFAULT_REPO", "")
    monkeypatch.setattr(pullrequest, "_plan", lambda c, p, cause: {"title": "T", "body": "", "diff": "d"})
    monkeypatch.setattr(governance, "leader", lambda: "Forge")
    res = pullrequest.propose("local-bot", "prod-1", "oops")   # no owner/name → no repo
    assert res["opened"] is False and res["proposed"] is True


def test_plan_fallback_when_no_model(monkeypatch):
    monkeypatch.setattr(pullrequest, "ENABLED", False)
    monkeypatch.setattr(pullrequest, "_plan", lambda c, p, cause: None)   # no LLM
    monkeypatch.setattr(governance, "leader", lambda: None)
    res = pullrequest.propose("Dashboard", "prod-1", "tests failing")
    assert res["proposed"] is True and "Dashboard" in res["title"]
