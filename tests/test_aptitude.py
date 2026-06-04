from maybot_control_center import governance, cultivation, agents


def test_model_iq_tiers(monkeypatch):
    defs = {"Op": {"model": "claude-opus-4-8"}, "So": {"model": "claude-sonnet-4-6"},
            "Ha": {"model": "claude-haiku-4-5"}, "Lo": {"model": "llama3"}, "No": {}}
    monkeypatch.setattr(agents, "_agent_def", lambda n: defs.get(n))
    assert governance._model_iq("Op") == 100
    assert governance._model_iq("So") == 78
    assert governance._model_iq("Ha") == 55
    assert governance._model_iq("Lo") == 50
    assert governance._model_iq("No") == 40


def test_aptitude_prefers_capable_model(monkeypatch):
    monkeypatch.setattr(agents, "_agent_def",
                        lambda n: {"model": "claude-opus-4-8"} if n == "Smart" else {"model": "llama3"})
    cultivation.clear()
    a_smart = governance.aptitude("Smart")["score"]
    a_dim = governance.aptitude("Dim")["score"]
    assert a_smart > a_dim
    assert set(governance.aptitude("Smart")["components"]) >= {"reasoning", "intelligence", "knowledge", "skills"}


def test_auto_leader_is_highest_aptitude(monkeypatch):
    monkeypatch.setattr(governance, "_all_agents", lambda: ["Smart", "Dim"])
    monkeypatch.setattr(governance, "aptitude",
                        lambda n: {"agent": n, "score": 90 if n == "Smart" else 20, "components": {}})
    governance.set_leader(None, pinned=False)   # release to merit/aptitude
    assert governance.leader() == "Smart"


def test_knowledge_and_skills_raise_aptitude(monkeypatch):
    monkeypatch.setattr(agents, "_agent_def", lambda n: {"model": "llama3"})
    cultivation.clear()
    base = governance.aptitude("Sage")["score"]
    cultivation.learn("Sage", "vector search")
    cultivation.learn("Sage", "reranking")
    assert governance.aptitude("Sage")["score"] > base
