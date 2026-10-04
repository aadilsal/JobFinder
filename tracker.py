"""Application pipeline per user in data/users/<uid>/out/applications.csv (drafted -> applied -> interviewing -> offer)."""
import csv
from datetime import date, timedelta
import config

FIELDS = ["id", "date", "company", "role", "match", "status", "applied_on", "follow_up",
          "contact", "contact_email", "job_url", "job_key", "folder", "notes", "source", "theme"]
POSITIVE = {"interviewing", "offer"}     # counted as "got a response" in insights
STATUSES = ["drafted", "applied", "follow-up sent", "interviewing", "offer", "rejected", "ghosted"]
ACTIVE = {"applied", "follow-up sent", "interviewing"}
FOLLOW_UP_DAYS = 7


def _file(uid):
    return config.out_dir(uid) / "applications.csv"


def load(uid):
    if not _file(uid).exists():
        return []
    with open(_file(uid), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, r in enumerate(rows, 1):
        for k in FIELDS:
            r[k] = r.get(k) or ""
        r["id"] = r["id"] or str(i)
    return rows


def save(uid, rows):
    with open(_file(uid), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows([normalize(r) for r in rows])


def normalize(r):
    """Applying stamps the date and schedules a follow-up a week later."""
    r = {k: ("" if r.get(k) is None or r.get(k) != r.get(k) else str(r.get(k))) for k in FIELDS}
    if r["status"] in ACTIVE and not r["applied_on"]:
        r["applied_on"] = date.today().isoformat()
    if r["status"] == "applied" and not r["follow_up"]:
        r["follow_up"] = (date.fromisoformat(r["applied_on"][:10]) + timedelta(days=FOLLOW_UP_DAYS)).isoformat()
    return r


def add(uid, **fields):
    rows = load(uid)
    row = {"id": str(max([int(r["id"]) for r in rows if r["id"].isdigit()] or [0]) + 1),
           "date": date.today().isoformat(), "status": "drafted", **fields}
    rows.append(row)
    save(uid, rows)
    return normalize(row)


def update(uid, row_id, **fields):
    rows = load(uid)
    hit = None
    for r in rows:
        if r["id"] == str(row_id):
            r.update({k: v for k, v in fields.items() if k in FIELDS and k != "id"})
            hit = r
    save(uid, rows)
    return normalize(hit) if hit else None


def get(uid, row_id):
    return next((r for r in load(uid) if r["id"] == str(row_id)), None)


def due_followups(uid, rows=None):
    today = date.today().isoformat()
    return [r for r in (rows if rows is not None else load(uid))
            if r["status"] in ("applied", "follow-up sent") and r["follow_up"] and r["follow_up"] <= today]
