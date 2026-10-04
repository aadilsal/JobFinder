"""The always-on loop: one shared scrape -> per user: rank, AI-score the best new jobs, push alerts, follow-up reminders.

  python cli.py cycle     # run once (cron / Task Scheduler)
  python cli.py watch     # run forever every scrape_every_hours
The web server (server.py) runs the same loop in a background thread.
"""
import json, os, threading, time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

import auth, config, generator, notify, prefs, scraper, tracker

STATUS = {"running": False, "log": [], "started": None, "finished": None, "error": None, "next_run": None}
_lock = threading.Lock()


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(path, data):
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def _ai_file(uid):
    return config.user_dir(uid) / "ai_scores.json"


def load_ai(uid):
    return _read(_ai_file(uid), {})


def attach_ai(uid, rows):
    ai = load_ai(uid)
    for r in rows:
        if a := ai.get(r["key"]):
            r.update(ai_match=a["match"], ai_verdict=a.get("verdict", ""), ai_strengths=a.get("strengths", []),
                     ai_gaps=a.get("gaps", []), eligible=a.get("eligible", "unclear"),
                     eligibility=a.get("eligibility", ""))
    return rows


def score_one(uid, job):
    """AI-score a single job on demand (from the job detail view)."""
    profile, _ = generator.load_inputs(uid)
    res = generator.match_job(job, profile, prefs.summary(uid))
    ai = load_ai(uid)
    ai[job["key"]] = {**res, "at": date.today().isoformat()}
    _write(_ai_file(uid), ai)
    return res


def score_new(uid, rows, cfg, log=print):
    if not os.getenv("ANTHROPIC_API_KEY"):
        log(f"[{uid}] AI scoring skipped (no ANTHROPIC_API_KEY) - alerts use the keyword score")
        return
    ai = load_ai(uid)
    todo = [r for r in rows if r["key"] not in ai and r["desc"] and r["score"] >= cfg["ai_prefilter_score"]]
    cap = cfg["ai_score_top_n"] if auth.is_admin(uid) else min(cfg["ai_score_top_n"], int(os.getenv("AI_SCORE_MAX_PER_SCAN", "15")))
    todo = todo[:cap]
    if not todo:
        return
    log(f"[{uid}] AI-scoring {len(todo)} jobs...")
    profile, _ = generator.load_inputs(uid)
    liked = prefs.summary(uid)

    def one(r):
        try:
            return r["key"], generator.match_job(r, profile, liked)
        except Exception as e:
            log(f"  ! AI score failed for {r['title'][:40]}: {e}")
            return r["key"], None

    with ThreadPoolExecutor(max_workers=4) as ex:
        for key, res in ex.map(one, todo):
            if res:
                ai[key] = {**res, "at": date.today().isoformat()}
    _write(_ai_file(uid), ai)


def match_of(r):
    """Percent used for alerts: the AI match when available, else the keyword score (only without an API key)."""
    if "ai_match" in r:
        return r["ai_match"]
    return 0 if os.getenv("ANTHROPIC_API_KEY") else min(r["score"], 100)


def alert(uid, rows, cfg, log=print):
    nf = config.user_dir(uid) / "notified.json"
    state = _read(nf, {"jobs": [], "followup_day": ""})
    done = set(state["jobs"])
    limit = cfg["alert_threshold"] if os.getenv("ANTHROPIC_API_KEY") else cfg["heuristic_alert_score"]
    hidden = {k for k, v in scraper.load_state(uid).items() if v == "hidden"}
    rows = [r for r in rows if r["key"] not in hidden and r.get("eligible") != "no"]   # never alert on jobs you can't take
    hits = sorted([r for r in rows if r["key"] not in done and match_of(r) >= limit], key=match_of, reverse=True)

    # new roles at companies you liked / shortlisted (even below the threshold)
    watched = {c.lower() for c in cfg.get("watch_companies", [])}
    hit_keys = {r["key"] for r in hits}
    for r in [r for r in rows if r["new"] and r["key"] not in done and r["key"] not in hit_keys
              and (r.get("company") or "").lower() in watched][:3]:
        notify.send(uid, f"New role at {r['company']}", f"{r['title']} - {r['location'] or 'location n/a'}",
                    path=f"/#/jobs/{r['key']}", tag=r["key"])
        hits.append(r)
        log(f"[{uid}] watched-company alert: {r['title']} @ {r['company']}")
    for r in hits[:5]:
        res = notify.send(uid, f"{match_of(r)}% match: {r['title']}",
                          f"{r['company']} - {r['location'] or 'location n/a'}\n{r.get('ai_verdict') or r['why']}",
                          path=f"/#/jobs/{r['key']}", tag=r["key"])
        log(f"[{uid}] alert: {r['title']} @ {r['company']} -> {res}")
    if len(hits) > 5:
        notify.send(uid, f"{len(hits) - 5} more strong matches", "Open jobkit to see them all.", path="/#/jobs")
    if not hits:
        log(f"[{uid}] no new jobs at or above {limit}%")
    state["jobs"] = sorted(done | {r["key"] for r in hits})

    today = date.today().isoformat()
    due = tracker.due_followups(uid)
    if due and state.get("followup_day") != today:
        # one due -> the notification opens a ready-written follow-up; several -> the applications list
        path = f"/#/outreach?app={due[0]['id']}&kind=follow_up&auto=1" if len(due) == 1 else "/#/applications?status=applied"
        notify.send(uid, f"{len(due)} follow-up{'s' if len(due) > 1 else ''} due today",
                    ", ".join(f"{r['role']} @ {r['company']}" for r in due[:4]), path=path)
        state["followup_day"] = today

    # morning digest: the day's best jobs you haven't been told about, including good 70-89% ones
    if cfg.get("daily_digest") and datetime.utcnow().hour >= cfg.get("digest_hour_utc", 4) \
            and state.get("digest_day") != today:
        sent = set(state.get("digested", []))
        best = sorted([r for r in rows if r["key"] not in sent and (match_of(r) >= 60 or r["score"] >= 60)],
                      key=lambda r: (match_of(r), r["score"]), reverse=True)[:5]
        if best:
            notify.send(uid, f"Today's top {len(best)} job{'s' if len(best) > 1 else ''} for you",
                        "\n".join(f"{match_of(r) or r['score']}% {r['title']} @ {r['company']}" for r in best),
                        path="/#/jobs?view=new", tag="digest")
            state["digested"] = sorted(sent | {r["key"] for r in best})[-500:]
            state["digest_day"] = today        # only once something was sent; otherwise retry next scan
            log(f"[{uid}] daily digest sent ({len(best)} jobs)")
    _write(nf, state)
    return hits


def active_users():
    return [u for u in auth.users() if config.profile_path(u).exists()]


def process_user(uid, pool, log=print):
    cfg = config.load(uid)
    rows = scraper.rank(pool, cfg, uid, log)
    score_new(uid, rows, cfg, log)
    return alert(uid, attach_ai(uid, rows), cfg, log)


def cycle(log=print, uids=None):
    uids = uids or active_users()
    if not uids:
        log("No users with a profile yet - nothing to do.")
        return
    pool = scraper.fetch(config.merged([config.load(u) for u in uids]), log=log)
    for uid in uids:
        try:
            process_user(uid, pool, log)
        except Exception as e:
            log(f"[{uid}] failed: {e}")


def rank_cached(uid, log=print):
    """Rank the last shared scrape for one user right away (e.g. straight after onboarding)."""
    pool = _read(scraper.RAW_FILE, [])
    return process_user(uid, pool, log) if pool else None


def run_async(target=None):
    """Run cycle() (or target) in the background; no-op if something is already running."""
    if not _lock.acquire(blocking=False):
        return False

    def log(msg):
        STATUS["log"] = (STATUS["log"] + [f"{datetime.now():%H:%M:%S} {msg}"])[-300:]

    def work():
        STATUS.update(running=True, log=[], started=datetime.now().isoformat(timespec="seconds"), error=None)
        try:
            (target or cycle)(log)
        except Exception as e:
            STATUS["error"] = str(e)
            log(f"ERROR: {e}")
        finally:
            STATUS.update(running=False, finished=datetime.now().isoformat(timespec="seconds"))
            _lock.release()

    threading.Thread(target=work, daemon=True).start()
    return True


def _hours():
    return max(1.0, float(os.getenv("SCRAPE_EVERY_HOURS", config.DEFAULTS["scrape_every_hours"])))


def schedule_forever(first_delay_s=60):
    """Background scheduler used by the server (interval from SCRAPE_EVERY_HOURS, default 6)."""
    def loop():
        delay = first_delay_s
        while True:
            STATUS["next_run"] = (datetime.now() + timedelta(seconds=delay)).isoformat(timespec="seconds")
            time.sleep(delay)
            run_async()
            delay = _hours() * 3600
    threading.Thread(target=loop, daemon=True).start()


def watch():
    while True:
        try:
            cycle()
        except Exception as e:
            print(f"cycle failed: {e}")
        print(f"Next run in {_hours()}h")
        time.sleep(_hours() * 3600)
