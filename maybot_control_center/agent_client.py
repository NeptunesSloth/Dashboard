import requests

_session = requests.Session()
_HEADERS = staticmethod = None  # unused, just for clarity


def _headers(token: str) -> dict:
    return {"x-api-token": token}


def _wrap(r: requests.Response) -> dict:
    return {
        "online": r.status_code < 500,
        "data": r.json() if r.headers.get("content-type", "").startswith("application/json") else {},
    }


def call_agent(device: dict, endpoint: str) -> dict:
    base = device.get("url", "").rstrip("/")
    token = device.get("api_token", "")
    try:
        r = _session.get(f"{base}{endpoint}", headers=_headers(token), timeout=5)
        return _wrap(r)
    except Exception as exc:
        return {"online": False, "error": str(exc), "data": {}}


def post_agent(device: dict, endpoint: str, timeout: int = 30) -> dict:
    base = device.get("url", "").rstrip("/")
    token = device.get("api_token", "")
    try:
        r = _session.post(f"{base}{endpoint}", headers=_headers(token), timeout=timeout)
        return _wrap(r)
    except Exception as exc:
        return {"online": False, "error": str(exc), "data": {}}
