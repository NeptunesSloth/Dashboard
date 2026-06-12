"""Account & identity routes (extracted from app.py): dashboard account CRUD
(operator-provisioned, no public sign-up), login + 2FA, first-run signup,
sessions, the current-user probe, password/2FA self-service, and Web Push
subscription.

Mounted by ``app.py`` via ``include_router``.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from .. import authz, notify, push
from ..config import CONTROL_CENTER_TOKEN
from ..deps import SAFE_NAME as _SAFE_NAME
from ..deps import check_operator as _check_operator
from ..deps import check_token as _check_token
from ..deps import mask_token as _mask_token

router = APIRouter()


# ---------------------------------------------------------------------------
# Account management — create/remove dashboard users from the UI (operator only).
# No public sign-up: an operator provisions accounts here, each gets a token.
# ---------------------------------------------------------------------------
class AccountIn(BaseModel):
    name: str
    role: str = "viewer"
    token: str = ""
    projects: list[str] | None = None
    original_name: str | None = None


@router.get("/api/accounts")
def accounts_list(x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    out = [{
        "name": u.get("name"), "role": u.get("role", "viewer"),
        "token_masked": _mask_token(u.get("token", "")), "has_token": bool(u.get("token")),
        "projects": u.get("projects") or [],
    } for u in authz.load_users()]
    return {"accounts": out, "auth_active": bool(authz.load_users())}


@router.post("/api/accounts")
def accounts_save(body: AccountIn, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    name = (body.name or "").strip()
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "account name may contain letters, numbers, dashes and underscores only")
    role = body.role if body.role in ("operator", "viewer") else "viewer"
    users = authz.load_users()
    was_empty = not users
    token = (body.token or "").strip() or secrets.token_hex(32)
    entry = {"name": name, "token": token, "role": role}
    if body.projects:
        entry["projects"] = body.projects
    if body.original_name:
        idx = next((i for i, u in enumerate(users) if u.get("name") == body.original_name.strip()), None)
        if idx is None:
            raise HTTPException(404, "account not found")
        if any(u.get("name") == name for i, u in enumerate(users) if i != idx):
            raise HTTPException(409, f"an account named '{name}' already exists")
        if not (body.token or "").strip() and users[idx].get("token"):
            entry["token"] = users[idx]["token"]
        users[idx] = entry
    else:
        if any(u.get("name") == name for u in users):
            raise HTTPException(409, f"an account named '{name}' already exists")
        users.append(entry)
    authz.save_users(users)
    # `first` tells the UI to adopt this token immediately (avoids a bootstrap lockout
    # the moment auth turns on); `token` is returned once so it can be copied.
    return {"ok": True, "name": name, "role": role, "token": entry["token"], "first": was_empty}


@router.delete("/api/accounts/{name}")
def accounts_delete(name: str, x_control_token: str = Header(default="")):
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid account name")
    users = authz.load_users()
    remaining = [u for u in users if u.get("name") != name]
    if len(remaining) == len(users):
        raise HTTPException(404, "account not found")
    # never strand the dashboard with users but no operator (would lock everyone out)
    if remaining and not any(u.get("role") == "operator" for u in remaining):
        raise HTTPException(409, "can't remove the last operator account")
    authz.save_users(remaining)
    return {"ok": True}


class ResetPwIn(BaseModel):
    new: str


@router.post("/api/accounts/{name}/reset-password")
def accounts_reset_password(name: str, body: ResetPwIn, x_control_token: str = Header(default="")):
    """Operator resets another account's password (e.g., a locked-out user)."""
    _check_operator(x_control_token)
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "invalid account name")
    if not authz.user_by_name(name):
        raise HTTPException(404, "account not found")
    if len(body.new or "") < 8:
        raise HTTPException(400, "new password must be at least 8 characters")
    authz.set_password(name, body.new)
    return {"ok": True}


# ---- Login / signup / account ----
class LoginIn(BaseModel):
    token: str = ""
    name: str = ""
    password: str = ""


def _issue(token: str) -> dict:
    session = authz.issue_session(token)
    out = {"ok": True, "role": authz.role_for(token), "name": authz.name_for(token)}
    if session:
        out["session"] = session["session"]
        out["expires"] = session["expires"]
    return out


@router.post("/api/login")
def login(body: LoginIn, request: Request):
    key = request.client.host if request.client else "anon"
    if authz.login_blocked(key):
        raise HTTPException(429, "too many sign-in attempts — wait a few minutes and try again")
    # Name + password sign-in (preferred). Falls back to raw-token login (legacy).
    if body.name and body.password:
        u = authz.user_by_name(body.name.strip())
        if not u or not u.get("pw") or not authz.verify_password(body.password, u.get("pw", "")):
            authz.note_login_fail(key)
            raise HTTPException(401, "invalid name or password")
        authz.reset_login(key)
        if u.get("totp"):
            cid, _ = authz.create_2fa_challenge(u["name"], method="totp")
            return {"ok": False, "pending_2fa": True, "challenge": cid, "method": "totp", "channel": "authenticator app"}
        if u.get("tfa") and notify.channels():
            cid, code = authz.create_2fa_challenge(u["name"], method="webhook")
            ch = notify.channels()[0]
            notify.send("Aegis sign-in code", f"Your 2FA code is {code} (valid 5 minutes).", level="info", kind="security")
            return {"ok": False, "pending_2fa": True, "challenge": cid, "method": "webhook", "channel": ch}
        return _issue(u["token"])
    role = authz.role_for(body.token)
    if role is None:
        authz.note_login_fail(key)
        raise HTTPException(401, "invalid token")
    authz.reset_login(key)
    return _issue(body.token)


class TwoFAIn(BaseModel):
    challenge: str = ""
    code: str = ""


@router.post("/api/login/2fa")
def login_2fa(body: TwoFAIn):
    name = authz.verify_2fa((body.challenge or "").strip(), (body.code or "").strip())
    if not name:
        raise HTTPException(401, "invalid or expired code")
    u = authz.user_by_name(name)
    if not u:
        raise HTTPException(401, "account no longer exists")
    return _issue(u["token"])


class SignupIn(BaseModel):
    name: str
    password: str


@router.post("/api/signup")
def signup(body: SignupIn):
    # Self-serve signup is allowed ONLY to claim a fresh dashboard (no accounts yet);
    # the first account becomes the owner/operator. After that, operators invite users.
    if authz.load_users():
        raise HTTPException(403, "sign-up is closed — ask an operator to create your account")
    name = (body.name or "").strip()
    if not _SAFE_NAME.match(name):
        raise HTTPException(400, "name may contain letters, numbers, dashes and underscores only")
    if len(body.password or "") < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    user = {"name": name, "token": secrets.token_hex(32), "role": "operator",
            "pw": authz.hash_password(body.password)}
    authz.save_users([user])
    return _issue(user["token"])


class LogoutIn(BaseModel):
    session: str = ""


@router.post("/api/logout")
def logout(body: LogoutIn):
    return {"ok": authz.revoke_session((body.session or "").strip())}


@router.get("/api/account/me")
def account_me(x_control_token: str = Header(default="")):
    """Who am I — used by the account bubble and the startup auth guard.
    Never 401s; returns authed=false so the client can route to /login."""
    users = authz.load_users()
    auth_active = bool(users) or bool(CONTROL_CENTER_TOKEN)
    role = authz.role_for(x_control_token)
    if role is None:
        return {"authed": False, "auth_active": auth_active, "accounts_exist": bool(users)}
    u = authz.current_user(x_control_token)
    return {
        "authed": True, "auth_active": auth_active, "accounts_exist": bool(users),
        "open_mode": not auth_active, "name": authz.name_for(x_control_token), "role": role,
        "has_password": bool(u and u.get("pw")), "tfa": bool(u and u.get("tfa")),
        "channels": notify.channels(),
    }


class PasswordIn(BaseModel):
    old: str = ""
    new: str


@router.post("/api/account/password")
def account_password(body: PasswordIn, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    u = authz.current_user(x_control_token)
    if not u:
        raise HTTPException(400, "no account is associated with this session")
    if u.get("pw") and not authz.verify_password(body.old, u.get("pw", "")):
        raise HTTPException(403, "current password is incorrect")
    if len(body.new or "") < 8:
        raise HTTPException(400, "new password must be at least 8 characters")
    authz.set_password(u["name"], body.new)
    return {"ok": True}


class TwoFAToggleIn(BaseModel):
    enable: bool
    method: str = "auto"   # "totp" (authenticator app), "webhook", or "auto"


@router.post("/api/account/2fa")
def account_2fa(body: TwoFAToggleIn, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    u = authz.current_user(x_control_token)
    if not u:
        raise HTTPException(400, "no account is associated with this session")
    if not body.enable:
        authz.set_totp(u["name"], None)    # also clears webhook tfa
        return {"ok": True, "tfa": False}
    method = body.method
    if method == "auto":
        method = "totp" if not notify.channels() else "webhook"
    if method == "totp":
        secret = authz.gen_totp_secret()
        authz.set_totp(u["name"], secret)
        return {"ok": True, "tfa": True, "method": "totp", "secret": secret,
                "uri": authz.totp_uri(u["name"], secret)}
    if not notify.channels():
        raise HTTPException(400, "set up a notification channel first, or use an authenticator app (method=totp)")
    authz.set_2fa(u["name"], True)
    return {"ok": True, "tfa": True, "method": "webhook"}


# ---- Web Push (VAPID) ----
@router.get("/api/push/key")
def push_key(x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    return push.public_key()


@router.post("/api/push/subscribe")
def push_subscribe(body: dict, x_control_token: str = Header(default="")):
    _check_token(x_control_token)
    try:
        return push.subscribe(body.get("subscription") or body)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
