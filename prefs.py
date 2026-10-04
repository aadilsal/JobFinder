"""Learns what each user wants from their thumbs up / down on jobs, and nudges ranking and AI scoring."""
import json, re
from datetime import date
import config

STOP = {"and", "the", "for", "with", "remote", "senior", "junior", "mid", "level", "engineer", "developer", "software",
        "full", "time", "team", "job", "role", "position", "hybrid", "onsite", "contract", "part"}


def _file(uid):
    return config.user_dir(uid) / "feedback.json"


def load(uid):
    f = _file(uid)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def record(uid, job, v):
    fb = load(uid)
    if v:
        fb[job["key"]] = {"v": 1 if v > 0 else -1, "title": job["title"], "company": job.get("company", ""),
                          "at": date.today().isoformat()}
    else:
        fb.pop(job["key"], None)
    _file(uid).write_text(json.dumps(fb, indent=1), encoding="utf-8")
    return fb


def tokens(title):
    words = re.findall(r"[a-z][a-z0-9+#.]{1,}", (title or "").lower())
    return {w.strip(".") for w in words if w.strip(".") not in STOP and len(w) > 2}


def weights(uid):
    """Title words and companies you liked (+) or disliked (-)."""
    w = {}
    for f in load(uid).values():
        for t in tokens(f["title"]):
            w[t] = w.get(t, 0) + f["v"]
        if f.get("company"):
            k = "co:" + f["company"].lower()
            w[k] = w.get(k, 0) + f["v"]
    return w


def adjust(job, w):
    """Score nudge in [-25, 25] from learned preferences."""
    if not w:
        return 0
    s = sum(max(-3, min(3, w.get(t, 0))) for t in tokens(job["title"])) * 3
    s += max(-2, min(2, w.get("co:" + (job.get("company") or "").lower(), 0))) * 6
    return max(-25, min(25, s))


def summary(uid):
    """Short text for the AI scorer: examples of what this person liked and skipped."""
    fb = list(load(uid).values())[-40:]
    liked = [f"{f['title']} @ {f['company']}" for f in fb if f["v"] > 0][-8:]
    disliked = [f"{f['title']} @ {f['company']}" for f in fb if f["v"] < 0][-8:]
    out = []
    if liked:
        out.append("Jobs they liked: " + "; ".join(liked))
    if disliked:
        out.append("Jobs they rejected: " + "; ".join(disliked))
    return "\n".join(out)
