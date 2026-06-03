import requests

_session = requests.Session()


def _headers(token: str) -> dict:
    return {"x-api-token": token}


def _wrap(r: requests.Response) -> dict:
    is_2xx = 200 <= r.status_code < 300
    is_auth_error = r.status_code in {401, 403}
    payload = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    error = None
    if not is_2xx:
        detail = payload.get("detail") if isinstance(payload, dict) else None
        error = detail or f"http status {r.status_code}"
    return {
        "online": is_2xx,
        "auth_error": is_auth_error,
        "status_code": r.status_code,
        "error": error,
        "data": payload,
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
