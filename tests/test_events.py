import json
import queue

from maybot_control_center import events


def test_publish_delivers_to_subscriber():
    q = events.subscribe()
    try:
        events.publish("agents", {"agent": "Nova"})
        msg = json.loads(q.get(timeout=1))
        assert msg["type"] == "agents"
        assert msg["data"]["agent"] == "Nova"
    finally:
        events.unsubscribe(q)


def test_unsubscribe_stops_delivery():
    q = events.subscribe()
    events.unsubscribe(q)
    events.publish("tools", {"id": 1})
    with __import__("pytest").raises(queue.Empty):
        q.get(timeout=0.1)
