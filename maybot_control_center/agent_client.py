import requests

_session = requests.Session()


def call_agent(device: dict, endpoint: str) -> dict:
    base = device.get("url", "").rstrip("/")
    token = device.get("api_token", "")
    try:
        r = _session.get(f"{base}{endpoint}", headers={"x-api-token": token}, timeout=5)
        return {
            "online": r.status_code == 200,
            "data": r.json() if r.headers.get("content-type", "").startswith("application/json") else {},
        }
    except Exception as exc:
        return {"online": False, "error": str(exc), "data": {}}
