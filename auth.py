"""Login with authenticator apps (TOTP). No passwords are stored anywhere.

Owner   : the first account registered on a fresh server becomes the admin (register right after deploying).
Friends : only by invite link. Admin taps "Create invite link" and sends it; the friend opens it, picks a
          username, scans a QR in Google Authenticator / Authy / 1Password / Microsoft Authenticator,
          confirms a 6-digit code, saves 8 recovery codes, then onboards with their own CV, GitHub etc.
          Links are single-use and expire after 7 days. Strangers who find the site can't register.
Log in  : username + current 6-digit code (or one recovery code)
Lost phone: admin "Reset authenticator" gives that user a personal re-enrol link (their data is kept).
"""
import hashlib, hmac, json, os, secrets, shutil, threading, time
from datetime import datetime

import pyotp
import config

USERS_FILE = config.DATA / "users.json"
INVITES_FILE = config.DATA / "invites.json"   # invite links + lost-phone re-enrol links
SECRET_FILE = config.DATA / "session_secret"
ISSUER = "jobkit"
SESSION_DAYS = 30
_lock = threading.Lock()
_pending = {}   # uid -> {"secret", "invite", "expires"} while the user scans the QR code
_fails = {}     # throttle key -> recent failure timestamps


class AuthError(Exception):
    pass


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path, data):
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def users():
    return _read(USERS_FILE, {})


def _hash(s):
    return hashlib.sha256(s.encode()).hexdigest()


def _key():
    if s := os.getenv("SESSION_SECRET"):
        return s.encode()
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
    return SECRET_FILE.read_text(encoding="utf-8").strip().encode()


def _throttle(*keys):
    """6 failures per username or 20 per IP (shared NATs) in 10 minutes -> wait."""
    now = time.time()
    for k in keys:
        _fails[k] = [t for t in _fails.get(k, []) if now - t < 600]
        if len(_fails[k]) >= (20 if k.startswith("ip:") else 6):
            raise AuthError("Too many attempts. Wait 10 minutes and try again.")


def _fail(*keys):
    for k in keys:
        _fails.setdefault(k, []).append(time.time())


# ---- sign up ---------------------------------------------------------------

INVITE_DAYS = 7


def _invite_live(inv):
    created = datetime.fromisoformat(inv["created"]).timestamp()
    return not inv.get("used_by") and not inv.get("revoked") and time.time() - created < INVITE_DAYS * 86400


def _find_invite(code, uid):
    for inv in _read(INVITES_FILE, []):
        if _invite_live(inv) and hmac.compare_digest(inv["code"], code):
            return inv
    return None


def invite_info(code):
    """What the join page shows: is the link usable, and is it a lost-phone re-enrol for a fixed username?"""
    inv = _find_invite((code or "").strip(), None)
    return {"valid": bool(inv), "for_user": inv.get("for_user") if inv else None}


def start_signup(uid, invite="", ip=""):
    uid = (uid or "").strip().lower()
    if not config.valid_uid(uid):
        raise AuthError("Username: 3-32 characters, lowercase letters, digits, - or _.")
    _throttle(f"ip:{ip}")
    us, invite = users(), (invite or "").strip()
    inv = _find_invite(invite, uid) if invite else None
    if not us:
        mode, inv = "first", None                # fresh server: the owner becomes admin
    elif not inv:
        _fail(f"ip:{ip}")
        raise AuthError("jobkit is invite-only. Ask the owner for an invite link (links expire after 7 days).")
    elif inv.get("for_user"):
        if inv["for_user"] != uid:
            raise AuthError(f"This link is for re-enrolling {inv['for_user']}.")
        mode = "reset"
    elif uid in us:
        raise AuthError("That username is taken.")
    else:
        mode = "invite"
    secret = pyotp.random_base32()
    _pending[uid] = {"secret": secret, "mode": mode, "invite": inv["code"] if inv else "", "expires": time.time() + 900}
    return secret, pyotp.TOTP(secret).provisioning_uri(name=uid, issuer_name=ISSUER)


def finish_signup(uid, code, ip=""):
    uid = (uid or "").strip().lower()
    p = _pending.get(uid)
    if not p or p["expires"] < time.time():
        raise AuthError("Sign-up expired. Start again.")
    _throttle(uid, f"ip:{ip}")
    if not pyotp.TOTP(p["secret"]).verify((code or "").replace(" ", ""), valid_window=1):
        _fail(uid, f"ip:{ip}")
        raise AuthError("That code didn't match. Make sure your phone's clock is set automatically, then try the next code.")
    recovery = [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(8)]
    with _lock:
        us = users()
        first = not us
        # re-check under the lock: someone may have claimed admin, used the link, or taken the username meanwhile
        if p["mode"] == "first" and not first:
            _pending.pop(uid, None)
            raise AuthError("The owner account already exists. You need an invite link.")
        if p["mode"] in ("invite", "reset"):
            inv = next((i for i in _read(INVITES_FILE, []) if i["code"] == p["invite"]), None)
            if not inv or not _invite_live(inv):
                _pending.pop(uid, None)
                raise AuthError("That link was already used or has expired. Ask the owner for a new one.")
        if p["mode"] == "invite" and uid in us:
            _pending.pop(uid, None)
            raise AuthError("Someone just took that username. Pick another one.")
        old = us.get(uid, {})
        us[uid] = {**old, "totp": p["secret"], "admin": old.get("admin", first),
                   "created": old.get("created", datetime.now().isoformat(timespec="seconds")),
                   "recovery": [_hash(r) for r in recovery], "last_step": 0, "revoked_before": int(time.time())}
        _write(USERS_FILE, us)
        if p["invite"]:
            invites = _read(INVITES_FILE, [])
            for inv in invites:
                if inv["code"] == p["invite"]:
                    inv["used_by"], inv["used_at"] = uid, datetime.now().isoformat(timespec="seconds")
            _write(INVITES_FILE, invites)
    _pending.pop(uid, None)
    legacy = config.ROOT / "profile.json"     # single-user jobkit: the first admin inherits the old profile
    if first and legacy.exists() and not config.profile_path(uid).exists():
        shutil.copy(legacy, config.profile_path(uid))
    return recovery, us[uid]["admin"]


# ---- log in / sessions -----------------------------------------------------

def login(uid, code, ip=""):
    uid, code = (uid or "").strip().lower(), (code or "").strip().replace(" ", "").lower()
    _throttle(uid, f"ip:{ip}")
    with _lock:
        us = users()
        u = us.get(uid)
        ok = False
        if u and code.isdigit() and len(code) == 6:
            totp, now_step = pyotp.TOTP(u["totp"]), int(time.time() // 30)
            for step in (now_step - 1, now_step, now_step + 1):
                if step > u.get("last_step", 0) and hmac.compare_digest(totp.at(step * 30), code):
                    u["last_step"], ok = step, True      # each code works once
                    break
        elif u and _hash(code) in u.get("recovery", []):
            u["recovery"].remove(_hash(code))
            ok = True
        if not ok:
            _fail(uid, f"ip:{ip}")
            raise AuthError("Invalid username or code.")
        _write(USERS_FILE, us)
    return make_token(uid)


def make_token(uid):
    now = int(time.time())
    payload = f"{uid}.{now}.{now + SESSION_DAYS * 86400}"
    return f"{payload}.{hmac.new(_key(), payload.encode(), hashlib.sha256).hexdigest()[:40]}"


def verify_token(token):
    try:
        uid, iat, exp, sig = (token or "").split(".")
        good = hmac.new(_key(), f"{uid}.{iat}.{exp}".encode(), hashlib.sha256).hexdigest()[:40]
        u = users().get(uid)
        if hmac.compare_digest(sig, good) and int(exp) > time.time() and u and int(iat) >= u.get("revoked_before", 0):
            return uid
    except ValueError:
        pass
    return None


def is_admin(uid):
    return bool(users().get(uid, {}).get("admin"))


# ---- admin -----------------------------------------------------------------

def create_invite(by, for_user=None):
    code = secrets.token_urlsafe(12)
    with _lock:
        invites = _read(INVITES_FILE, [])
        invites.append({"code": code, "by": by, "for_user": for_user, "used_by": None,
                        "created": datetime.now().isoformat(timespec="seconds")})
        _write(INVITES_FILE, invites)
    return code


def reset_user(uid, by):
    """Log the user out everywhere and give them a code to re-enrol a new authenticator (their data is kept)."""
    with _lock:
        us = users()
        if uid not in us:
            raise AuthError("No such user.")
        us[uid]["revoked_before"] = int(time.time()) + 1
        _write(USERS_FILE, us)
    return create_invite(by, for_user=uid)


def list_invites():
    return [{**i, "status": "used" if i.get("used_by") else "revoked" if i.get("revoked")
             else "active" if _invite_live(i) else "expired"} for i in _read(INVITES_FILE, [])]


def revoke_invite(code):
    with _lock:
        invites = _read(INVITES_FILE, [])
        for inv in invites:
            if inv["code"] == code and not inv.get("used_by"):
                inv["revoked"] = True
        _write(INVITES_FILE, invites)


def delete_user(uid):
    """Removes the account. Their files stay in data/users/<uid> until you delete them by hand."""
    with _lock:
        us = users()
        us.pop(uid, None)
        _write(USERS_FILE, us)


def public_users():
    return [{"uid": k, "admin": v.get("admin", False), "created": v.get("created"),
             "recovery_left": len(v.get("recovery", [])),
             "has_profile": config.profile_path(k).exists()} for k, v in users().items()]
