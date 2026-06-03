"""Mission board: quests a disciple can undertake to earn a unique technique.

Dispatching a quest assigns the disciple the quest's task; on success the
disciple brings back the quest's reward technique (a new skill) plus spirit
stones (see cultivation.assign_quest / on_task).
"""
from __future__ import annotations

QUESTS = {
    "patrol": {"name": "Patrol the Mountain Gate", "reward_skill": "Sentinel's Eye", "stones": 30,
               "task": "Patrol the sect's defenses: review the projects/realms' health and report any weakness as terse bullets."},
    "gather": {"name": "Gather Spirit Herbs", "reward_skill": "Herbal Lore", "stones": 25,
               "task": "Survey the available resources and metrics; summarize what is plentiful and what is scarce."},
    "scout": {"name": "Scout the Rival Sect", "reward_skill": "Far-Sight Art", "stones": 40,
              "task": "Research the topic the master will provide and bring back the three most important findings."},
    "trial": {"name": "Trial of Insight", "reward_skill": "Dao Comprehension", "stones": 50,
              "task": "Reflect on the sect's current goals and propose the single highest-leverage next step, with rationale."},
}


def catalog() -> list[dict]:
    return [{"id": k, "name": v["name"], "reward_skill": v["reward_skill"], "stones": v["stones"]}
            for k, v in QUESTS.items()]


def get(quest_id: str) -> dict | None:
    return QUESTS.get(quest_id)
