from maybot_control_center import github_repo


def setup_function():
    github_repo.clear()


def _fake(metrics_by_repo):
    return lambda repo: metrics_by_repo[repo]


def test_collect_maps_repos_to_projects(monkeypatch):
    monkeypatch.setattr(github_repo, "REPOS", ["owner/clean", "owner/busy", "owner/broken"])
    f = _fake({
        "owner/clean": {"open_prs": 1, "open_issues": 2, "failing_checks": 0},
        "owner/busy": {"open_prs": 12, "open_issues": 3, "failing_checks": 0},
        "owner/broken": {"open_prs": 1, "open_issues": 0, "failing_checks": 2},
    })
    projects = github_repo.collect(fetcher=f)
    by_name = {p["name"]: p for p in projects}
    assert all(p["type"] == "github_repo" and p["device"] == "github" for p in projects)
    assert by_name["owner/clean"]["health"] == "ok"
    assert by_name["owner/busy"]["health"] == "warning"   # open PRs over the warn threshold
    assert by_name["owner/broken"]["health"] == "error"   # failing checks
    assert any("failing checks" in a for a in by_name["owner/broken"]["alerts"])


def test_fetch_error_becomes_unhealthy(monkeypatch):
    monkeypatch.setattr(github_repo, "REPOS", ["owner/x"])

    def boom(repo):
        raise RuntimeError("gh not authenticated")

    p = github_repo.collect(fetcher=boom)[0]
    assert p["health"] == "error"
    assert "gh not authenticated" in p["metrics"]["error"]
    assert any("ERROR" in a for a in p["alerts"])


def test_results_are_cached(monkeypatch):
    monkeypatch.setattr(github_repo, "REPOS", ["owner/x"])
    calls = {"n": 0}

    def counting(repo):
        calls["n"] += 1
        return {"open_prs": 0, "open_issues": 0, "failing_checks": 0}

    github_repo.collect(fetcher=counting)
    github_repo.collect(fetcher=counting)  # within TTL → served from cache
    assert calls["n"] == 1


def test_enabled_reflects_config(monkeypatch):
    monkeypatch.setattr(github_repo, "REPOS", [])
    assert github_repo.enabled() is False
    monkeypatch.setattr(github_repo, "REPOS", ["a/b"])
    assert github_repo.enabled() is True


def test_task_reference_formats(monkeypatch):
    assert github_repo.task_reference("") == ""
    assert github_repo.task_reference("owner/x") == "[GitHub context: owner/x]"
    ref = github_repo.task_reference("owner/x", 42, fetcher=lambda r: {"open_prs": 0})
    assert ref.startswith("[GitHub context: owner/x#42]")
