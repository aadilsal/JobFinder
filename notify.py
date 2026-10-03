"""Phone notifications per user: Web Push to the installed PWA, plus optional ntfy and Telegram.

Web Push  - tap "Enable notifications" in the app (needs HTTPS; on iPhone add the app to your
            Home Screen first, iOS 16.4+). Works on as many devices as you enable it on.
ntfy      - put a long random topic in Settings, install the ntfy app and subscribe to that topic.
Telegram  - server admin sets TELEGRAM_BOT_TOKEN; each user puts their chat id in Settings.
"""
import base64, json, os
import requests
import config

VAPID_FILE = config.DATA / "vapid_private.pem"


def _vapid():
    from py_vapid import Vapid01
    if not VAPID_FILE.exists():
        v = Vapid01()
        v.generate_keys()
        v.save_key(str(VAPID_FILE))
    return Vapid01.from_file(str(VAPID_FILE))


def vapid_public_key():
    from cryptography.hazmat.primitives import serialization
    raw = _vapid().public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _subs_file(uid):
    return config.user_dir(uid) / "push_subscriptions.json"


def _subs(uid):
    f = _subs_file(uid)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def subscribe(uid, sub):
    subs = [s for s in _subs(uid) if s.get("endpoint") != sub.get("endpoint")] + [sub]
    _subs_file(uid).write_text(json.dumps(subs, indent=1), encoding="utf-8")
    return len(subs)


def unsubscribe(uid, endpoint):
    _subs_file(uid).write_text(json.dumps([s for s in _subs(uid) if s.get("endpoint") != endpoint]), encoding="utf-8")


def channels(uid):
    cfg = config.load(uid)
    return {"web_push_devices": len(_subs(uid)), "ntfy": bool(cfg.get("ntfy_topic")),
            "telegram": bool(os.getenv("TELEGRAM_BOT_TOKEN") and cfg.get("telegram_chat_id"))}


def _absolute(path):
    base = os.getenv("PUBLIC_URL", "").rstrip("/")
    return f"{base}/{path.lstrip('/')}" if base and not path.startswith("http") else path


def send(uid, title, body, path="/", tag=None):
    """Send to every channel this user configured. Returns {channel: delivered_count or error}."""
    cfg, result = config.load(uid), {}
    subs = _subs(uid)
    if subs:
        from pywebpush import webpush, WebPushException
        _vapid()
        keep, ok = [], 0
        payload = json.dumps({"title": title, "body": body, "url": path, "tag": tag})
        for s in subs:
            try:
                webpush(subscription_info=s, data=payload, vapid_private_key=str(VAPID_FILE), ttl=86400,
                        vapid_claims={"sub": f"mailto:{os.getenv('VAPID_EMAIL', 'admin@jobkit.local')}"})
                ok += 1
                keep.append(s)
            except WebPushException as e:
                if not (e.response is not None and e.response.status_code in (404, 410)):
                    keep.append(s)   # transient failure: keep; 404/410 means the device unsubscribed
        _subs_file(uid).write_text(json.dumps(keep, indent=1), encoding="utf-8")
        result["web_push"] = ok
    if topic := cfg.get("ntfy_topic"):
        msg = {"topic": topic, "title": title, "message": body, "priority": 4, "tags": ["briefcase"]}
        if (click := _absolute(path)).startswith("http"):
            msg["click"] = click
        try:
            requests.post(os.getenv("NTFY_SERVER", "https://ntfy.sh"), json=msg, timeout=15).raise_for_status()
            result["ntfy"] = 1
        except Exception as e:
            result["ntfy"] = f"error: {e}"
    if (tok := os.getenv("TELEGRAM_BOT_TOKEN")) and (chat := cfg.get("telegram_chat_id")):
        link = _absolute(path)
        try:
            requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=15,
                          json={"chat_id": chat, "text": f"{title}\n{body}" + (f"\n{link}" if link.startswith("http") else "")}
                          ).raise_for_status()
            result["telegram"] = 1
        except Exception as e:
            result["telegram"] = f"error: {e}"
    return result
