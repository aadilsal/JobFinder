"""jobkit web server: installable PWA + JSON API + background job watcher.

  python cli.py serve                     # local: http://127.0.0.1:8000
  docker compose up -d                    # production (see README > Deploy)
"""
import base64, json, os, re, threading, time
from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config, auth, applier, generator, github_sync, notify, render, scraper, tracker, watcher

COOKIE = "jk_session"
WEB = config.ROOT / "web"


@asynccontextmanager
async def lifespan(app):
    if os.getenv("DISABLE_SCHEDULER") != "1":
        watcher.schedule_forever()
    yield


app = FastAPI(title="jobkit", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def guard(request: Request, call_next):
    # CSRF: state-changing API calls must carry a custom header, which other sites can't send without CORS
    if request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD") \
            and request.headers.get("x-requested-with") != "jobkit":
        return JSONResponse({"detail": "Missing X-Requested-With header"}, status_code=403)
    resp = await call_next(request)
    resp.headers.update({"X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin",
                         "X-Frame-Options": "SAMEORIGIN"})
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.exception_handler(auth.AuthError)
async def auth_error(_, e):
    return JSONResponse({"detail": str(e)}, status_code=400)


def ip(request: Request):
    return request.client.host if request.client else ""



def user(request: Request):
    uid = auth.verify_token(request.cookies.get(COOKIE))
    if not uid:
        raise HTTPException(401, "Please log in")
    return uid


def admin(uid=Depends(user)):
    if not auth.is_admin(uid):
        raise HTTPException(403, "Admins only")
    return uid


def _set_session(resp: Response, request: Request, token):
    resp.set_cookie(COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", path="/")


def _err(e, code=400):
    raise HTTPException(code, str(e))


def _quiet(fn, *a):
    try:
        fn(*a)
    except Exception as e:
        print(f"background {fn.__name__} failed: {e}")


AI_DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "30"))   # per non-admin user: CV parses, tailors, outreach, scores


def spend_ai(uid):
    """Invited friends share your Anthropic key - cap each non-admin user's daily AI actions."""
    if not os.getenv("ANTHROPIC_API_KEY") or AI_DAILY_LIMIT <= 0 or auth.is_admin(uid):
        return
    f = config.user_dir(uid) / "usage.json"
    today = time.strftime("%Y-%m-%d")
    u = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    if u.get("day") != today:
        u = {"day": today, "ai": 0}
    if u["ai"] >= AI_DAILY_LIMIT:
        _err(f"You've used today's {AI_DAILY_LIMIT} AI actions. They reset tomorrow.", 429)
    u["ai"] += 1
    f.write_text(json.dumps(u), encoding="utf-8")


# ---- auth ------------------------------------------------------------------

@app.get("/api/auth/status")
def auth_status():
    return {"first_user": not auth.users()}


@app.get("/api/auth/invite/{code}")
def invite_check(code: str):
    return auth.invite_info(code)


@app.post("/api/auth/signup/start")
def signup_start(request: Request, body: dict = Body(...)):
    import segno
    secret, uri = auth.start_signup(body.get("uid", ""), body.get("invite", ""), ip(request))
    return {"secret": secret, "uri": uri, "qr": segno.make(uri, error="m").svg_data_uri(scale=6, border=2)}


@app.post("/api/auth/signup/finish")
def signup_finish(request: Request, response: Response, body: dict = Body(...)):
    uid = body.get("uid", "").strip().lower()
    recovery, is_admin = auth.finish_signup(uid, body.get("code", ""), ip(request))
    _set_session(response, request, auth.make_token(uid))
    return {"recovery": recovery, "admin": is_admin}


@app.post("/api/auth/login")
def login(request: Request, response: Response, body: dict = Body(...)):
    _set_session(response, request, auth.login(body.get("uid", ""), body.get("code", ""), ip(request)))
    return {"ok": True}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/me")
def me(uid=Depends(user)):
    has, cfg = config.profile_path(uid).exists(), config.load(uid)
    prof = generator.load_inputs(uid)[0] if has else {}
    questions = generator.profile_gaps(prof) if has else []
    return {"uid": uid, "admin": auth.is_admin(uid), "has_profile": has,
            "onboarded": has and not any(q["required"] for q in questions),
            "ai": bool(os.getenv("ANTHROPIC_API_KEY")), "channels": notify.channels(uid),
            "threshold": cfg["alert_threshold"], "cv_theme": cfg["cv_theme"], "name": prof.get("name", ""),
            "school": ((prof.get("education") or [{}])[0].get("school") or "").split(",")[0]}


def _disposition(kind, filename):
    """Content-Disposition with a readable name ('Aadil Salman Butt CV.pdf'), safe for any characters."""
    from urllib.parse import quote
    ascii_name = filename.encode("ascii", "ignore").decode() or "file.pdf"
    return f'{kind}; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'


def _watch(uid, job):
    """You showed interest in a company: watch its whole job board and boost/alert its new roles."""
    cfg, changed = config.load(uid), False
    co = (job.get("company") or "").strip()
    if co and co.lower() not in [c.lower() for c in cfg["watch_companies"]]:
        cfg["watch_companies"].append(co)
        changed = True
    if (ats := scraper.detect_ats(job.get("url"))) and ats[1] not in cfg["ats_companies"].setdefault(ats[0], []):
        cfg["ats_companies"][ats[0]].append(ats[1])
        changed = True
    if changed:
        config.save(uid, cfg)
    return co if changed else ""


# ---- onboarding + profile --------------------------------------------------

@app.post("/api/profile/parse")
def profile_parse(uid=Depends(user), body: dict = Body(...)):
    data = base64.b64decode(body.get("data_b64", "") or b"")
    if not data or len(data) > 8_000_000:
        _err("Upload a CV under 8 MB (PDF, DOCX or TXT).")
    if not os.getenv("ANTHROPIC_API_KEY"):
        _err("CV parsing needs ANTHROPIC_API_KEY on the server. Fill the form manually instead.")
    spend_ai(uid)
    try:
        p = generator.parse_cv(data, body.get("filename", "cv.pdf"))
    except Exception as e:
        _err(f"Couldn't read that CV: {e}")
    return {"profile": p, "questions": generator.profile_gaps(p)}


@app.post("/api/profile/suggest")
def profile_suggest(uid=Depends(user), body: dict = Body(...)):
    """Fill target roles, headline, years and work preferences. overwrite=False only fills blanks."""
    p = generator.normalize_profile(body.get("profile") or {})
    if os.getenv("ANTHROPIC_API_KEY"):
        spend_ai(uid)
    try:
        s = generator.suggest_fields(p)
    except Exception as e:
        _err(f"Couldn't suggest right now: {e}")
    p = {**p, **s} if body.get("overwrite") else generator.fill_blanks(p, s)
    return {"profile": p, "suggested": s, "questions": generator.profile_gaps(p)}


@app.post("/api/profile/answers")
def profile_answers(uid=Depends(user), body: dict = Body(...)):
    p = generator.apply_answers(generator.normalize_profile(body.get("profile") or {}), body.get("answers") or {})
    return {"profile": p, "questions": generator.profile_gaps(p)}


@app.get("/api/profile")
def profile_get(uid=Depends(user)):
    if not config.profile_path(uid).exists():
        p = generator.normalize_profile({})
    else:
        p = generator.load_inputs(uid)[0]
    return {"profile": p, "questions": generator.profile_gaps(p)}


@app.put("/api/profile")
def profile_put(uid=Depends(user), body: dict = Body(...)):
    p = generator.normalize_profile(body.get("profile") or {})
    if not p.get("name"):
        _err("Name is required.")
    first_time = not (config.user_dir(uid) / "config.json").exists()
    config.profile_path(uid).write_text(json.dumps(p, indent=2), encoding="utf-8")
    if first_time or body.get("rebuild_search"):
        cfg = generator.search_from_profile(p, config.load(uid))
        config.save(uid, cfg)
        watcher.run_async(lambda log: watcher.rank_cached(uid, log))   # show matches from the last scrape now
        if first_time and cfg.get("github_user"):                      # pull their repos as CV projects
            threading.Thread(target=lambda: _quiet(github_sync.sync, uid), daemon=True).start()
    return {"profile": p, "questions": generator.profile_gaps(p)}


@app.get("/api/themes")
def themes(uid=Depends(user)):
    return [{"id": k, "label": v["label"], "accent": v["accent"]} for k, v in render.THEMES.items()]


@app.get("/api/cv/base/{theme}")
def cv_base(theme: str, uid=Depends(user)):
    if theme not in render.THEMES:
        _err("Unknown theme", 404)
    name = applier.download_name(generator.load_inputs(uid)[0], "CV.pdf")
    return FileResponse(applier.base_cv(uid, theme), media_type="application/pdf",
                        headers={"Content-Disposition": _disposition("inline", name)})


# ---- jobs ------------------------------------------------------------------

def _jobs(uid):
    import prefs
    state, fb = scraper.load_state(uid), prefs.load(uid)
    return [{**r, "state": state.get(r["key"], ""), "feedback": fb.get(r["key"], {}).get("v", 0)}
            for r in watcher.attach_ai(uid, scraper.load_jobs(uid))]


@app.get("/api/jobs")
def jobs(uid=Depends(user)):
    return [{k: v for k, v in r.items() if k != "desc"} for r in _jobs(uid)]


def _job(uid, key):
    j = next((r for r in _jobs(uid) if r["key"] == key), None)
    if not j:
        _err("Job not found (it may have dropped out of the latest scrape)", 404)
    return j


@app.get("/api/jobs/{key}")
def job_detail(key: str, uid=Depends(user)):
    return _job(uid, key)


@app.post("/api/jobs/{key}/state")
def job_state(key: str, uid=Depends(user), body: dict = Body(...)):
    if body.get("state") not in ("", "shortlisted", "hidden", "applied"):
        _err("bad state")
    scraper.set_state(uid, key, body["state"])
    watched = _watch(uid, _job(uid, key)) if body["state"] == "shortlisted" else ""
    return {"ok": True, "watching": watched}


@app.post("/api/jobs/{key}/feedback")
def job_feedback(key: str, uid=Depends(user), body: dict = Body(...)):
    """Thumbs up (1) / down (-1) / clear (0). Teaches ranking + AI scoring what you want."""
    import prefs
    v = int(body.get("v", 0))
    job = _job(uid, key)
    prefs.record(uid, job, v)
    watched = ""
    if v > 0:
        watched = _watch(uid, job)
    elif v < 0:
        scraper.set_state(uid, key, "hidden")
    return {"ok": True, "watching": watched}


@app.post("/api/jobs/{key}/score")
def job_score(key: str, uid=Depends(user)):
    if not os.getenv("ANTHROPIC_API_KEY"):
        _err("AI scoring needs ANTHROPIC_API_KEY")
    job = _job(uid, key)
    spend_ai(uid)
    return watcher.score_one(uid, job)


@app.post("/api/jobs/{key}/apply")
def job_apply(key: str, uid=Depends(user), body: dict = Body(default={})):
    job = _job(uid, key)
    spend_ai(uid)
    name, c, row = applier.apply(uid, "", job=job, theme=body.get("theme"))
    _watch(uid, job)
    return {"folder": name, "tailored": c, "application": row}


# ---- apply from pasted JD / URL + packages ---------------------------------

@app.post("/api/apply")
def apply(uid=Depends(user), body: dict = Body(...)):
    jd = (body.get("jd") or "").strip()
    if not jd and body.get("url"):
        try:
            jd = applier.fetch_url(body["url"].strip())
        except Exception as e:
            _err(e)
    if len(jd) < 80:
        _err("Paste the job description (or a public job URL).")
    spend_ai(uid)
    name, c, row = applier.apply(uid, jd, body.get("company", ""), theme=body.get("theme"))
    return {"folder": name, "tailored": c, "application": row}


@app.get("/api/packages/{name}")
def package(name: str, uid=Depends(user)):
    try:
        return applier.load_package(uid, name)
    except FileNotFoundError:
        _err("Not found", 404)


@app.post("/api/packages/{name}/render")
def package_render(name: str, uid=Depends(user), body: dict = Body(...)):
    try:
        return {"tailored": applier.rerender(uid, name, body.get("edits") or {}, body.get("theme"))}
    except FileNotFoundError:
        _err("Not found", 404)


@app.get("/api/packages/{name}/files/{fname}")
def package_file(name: str, fname: str, uid=Depends(user), download: int = 0):
    try:
        base = applier.folder(uid, name)
    except FileNotFoundError:
        _err("Not found", 404)
    p = (base / fname).resolve()
    if p.parent != base or not p.is_file():
        _err("Not found", 404)
    nice = applier.download_name(generator.load_inputs(uid)[0], p.name)
    return FileResponse(p, headers={"Content-Disposition": _disposition("attachment" if download else "inline", nice)})


@app.post("/api/packages/{name}/answers")
def package_answers(name: str, uid=Depends(user)):
    """Ready-to-paste answers for the application form (incl. the posting's own questions)."""
    try:
        pkg = applier.load_package(uid, name)
    except FileNotFoundError:
        _err("Not found", 404)
    if not os.getenv("ANTHROPIC_API_KEY"):
        _err("Form answers need ANTHROPIC_API_KEY on the server.")
    spend_ai(uid)
    profile, gh = generator.load_inputs(uid)
    c = pkg["tailored"]
    answers = generator.form_answers(profile, gh, pkg["jd"], c.get("company", ""), c.get("role", ""))
    applier.save_extra(uid, name, "answers", answers)
    return {"answers": answers}


@app.post("/api/packages/{name}/interview")
def package_interview(name: str, uid=Depends(user)):
    """Interview prep pack: company brief, likely questions with your answers, questions to ask them."""
    try:
        pkg = applier.load_package(uid, name)
    except FileNotFoundError:
        _err("Not found", 404)
    if not os.getenv("ANTHROPIC_API_KEY"):
        _err("Interview prep needs ANTHROPIC_API_KEY on the server.")
    spend_ai(uid)
    profile, gh = generator.load_inputs(uid)
    c = pkg["tailored"]
    prep = generator.interview_prep(profile, gh, pkg["jd"], c.get("company", ""), c.get("role", ""))
    applier.save_extra(uid, name, "interview", prep)
    return {"interview": prep}


# ---- applications + outreach -----------------------------------------------

@app.get("/api/applications")
def applications(uid=Depends(user)):
    return {"rows": tracker.load(uid), "statuses": tracker.STATUSES}


@app.patch("/api/applications/{row_id}")
def application_update(row_id: str, uid=Depends(user), body: dict = Body(...)):
    if body.get("status") and body["status"] not in tracker.STATUSES:
        _err("bad status")
    row = tracker.update(uid, row_id, **body)
    if not row:
        _err("Not found", 404)
    return row


@app.post("/api/outreach")
def outreach(uid=Depends(user), body: dict = Body(...)):
    kind = body.get("kind", "cold_email")
    if kind not in generator.OUTREACH:
        _err("Unknown message type")
    profile, gh = generator.load_inputs(uid)
    jd, row = body.get("jd", ""), None
    if body.get("app_id"):
        row = tracker.get(uid, body["app_id"])
        if row and row["folder"]:
            try:
                jd = jd or applier.load_package(uid, row["folder"])["jd"]
            except FileNotFoundError:
                pass
    company = body.get("company") or (row or {}).get("company", "")
    role = body.get("role") or (row or {}).get("role", "")
    spend_ai(uid)
    try:
        m = generator.outreach(kind, profile, gh, company, role, body.get("recipient", ""), jd, body.get("notes", ""))
    except Exception as e:
        _err(f"Generation failed: {e}")
    if row and row["folder"]:
        try:
            with open(applier.folder(uid, row["folder"]) / "outreach.md", "a", encoding="utf-8") as f:
                f.write(f"\n## {kind} ({time.strftime('%Y-%m-%d')})\n" +
                        (f"Subject: {m['subject']}\n\n" if m.get("subject") else "") + m["body"] + "\n")
        except FileNotFoundError:
            pass
    return m


# ---- overview + scraping ---------------------------------------------------

@app.get("/api/overview")
def overview(uid=Depends(user)):
    cfg, rows, apps = config.load(uid), _jobs(uid), tracker.load(uid)
    thr = cfg["alert_threshold"]
    visible = [r for r in rows if r["state"] != "hidden"]
    by_status = {s: sum(a["status"] == s for a in apps) for s in tracker.STATUSES}
    by_source = {}
    for r in rows:
        src = r["source"].split("/")[0]
        by_source[src] = by_source.get(src, 0) + 1
    top = sorted(visible, key=lambda r: (watcher.match_of(r), r["score"]), reverse=True)[:8]
    meta = scraper.load_meta()
    return {
        "kpis": {"matched": len(rows), "new": sum(r["new"] for r in rows),
                 "strong": sum(watcher.match_of(r) >= thr for r in visible),
                 "ai_scored": sum("ai_match" in r for r in rows),
                 "shortlisted": sum(r["state"] == "shortlisted" for r in rows),
                 "applications": len(apps), "active": sum(a["status"] in tracker.ACTIVE for a in apps),
                 "interviews": by_status["interviewing"], "offers": by_status["offer"]},
        "threshold": thr, "by_status": by_status, "by_source": by_source,
        "followups": tracker.due_followups(uid, apps),
        "top": [{k: v for k, v in r.items() if k != "desc"} for r in top],
        "last_run": meta.get("last_run"), "sources": meta.get("sources", {}),
        "watcher": {k: watcher.STATUS[k] for k in ("running", "started", "finished", "next_run")},
        "insights": _insights(apps),
        "todo": {"drafts": sum(a["status"] == "drafted" for a in apps),
                 "strong_unseen": sum(watcher.match_of(r) >= thr and r["new"] and not r["state"] for r in visible),
                 "unscored_shortlist": sum(r["state"] == "shortlisted" and "ai_match" not in r for r in rows),
                 "notifications": any(notify.channels(uid).values()),
                 "github": bool(github_sync.load(uid))},
    }


def _insights(apps):
    """What's working: reply rate (interviewing/offer) by source, CV design and match score."""
    sent = [a for a in apps if a["status"] not in ("drafted", "")]
    if not sent:
        return {"sent": 0}

    def group(key):
        out = {}
        for a in sent:
            g = key(a) or "unknown"
            d = out.setdefault(g, {"sent": 0, "responses": 0})
            d["sent"] += 1
            d["responses"] += a["status"] in tracker.POSITIVE
        return sorted(({"name": k, **v, "rate": round(100 * v["responses"] / v["sent"])} for k, v in out.items()),
                      key=lambda x: (-x["rate"], -x["sent"]))

    def bucket(a):
        try:
            m = int(float(a["match"] or 0))
        except ValueError:
            return "unknown"
        return "80+" if m >= 80 else "60-79" if m >= 60 else "under 60"

    responses = sum(a["status"] in tracker.POSITIVE for a in sent)
    return {"sent": len(sent), "responses": responses, "rate": round(100 * responses / len(sent)),
            "by_source": group(lambda a: a.get("source")), "by_theme": group(lambda a: a.get("theme")),
            "by_match": group(bucket)}


@app.post("/api/scrape")
def scrape(uid=Depends(user)):
    last = scraper.load_meta().get("last_run")
    recent = bool(last) and (time.time() - time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%S"))) < 1800
    if recent and not auth.is_admin(uid):
        return {"started": watcher.run_async(lambda log: watcher.rank_cached(uid, log)),
                "mode": "re-rank (sources were scraped under 30 minutes ago)"}
    return {"started": watcher.run_async(), "mode": "full scrape"}


@app.get("/api/scrape/status")
def scrape_status(uid=Depends(user)):
    tag = re.compile(r" \[([a-z0-9_-]+)\] ")   # per-user lines look like "12:00:01 [uid] ..."
    mine = [l for l in watcher.STATUS["log"] if not (m := tag.search(l)) or m.group(1) == uid]
    return {**{k: v for k, v in watcher.STATUS.items() if k != "log"}, "log": mine[-120:]}


# ---- settings, github, notifications ---------------------------------------

@app.get("/api/settings")
def settings(uid=Depends(user)):
    out = {"config": config.load(uid), "channels": notify.channels(uid),
           "sources": list(scraper.SOURCES), "themes": themes(uid)}
    if auth.is_admin(uid):
        out["env"] = config.env_status()
    return out


@app.put("/api/settings")
def settings_put(uid=Depends(user), body: dict = Body(...)):
    cfg = config.load(uid)
    for k, v in (body.get("config") or {}).items():
        d = config.DEFAULTS.get(k)
        if d is None or isinstance(d, bool) != isinstance(v, bool):
            continue
        if type(v) is type(d) or (isinstance(d, (int, float)) and isinstance(v, (int, float))):
            cfg[k] = v
    config.save(uid, cfg)
    return {"config": cfg}


@app.get("/api/github")
def github(uid=Depends(user)):
    return {"repos": github_sync.load(uid), "user": config.load(uid).get("github_user", "")}


@app.post("/api/github/sync")
def github_sync_now(uid=Depends(user)):
    try:
        return {"repos": github_sync.sync(uid)}
    except Exception as e:
        _err(e)


@app.post("/api/github/{name}")
def github_include(name: str, uid=Depends(user), body: dict = Body(...)):
    github_sync.set_include(uid, name, bool(body.get("include")))
    return {"ok": True}


@app.get("/api/push/key")
def push_key(uid=Depends(user)):
    return {"key": notify.vapid_public_key()}


@app.post("/api/push/subscribe")
def push_subscribe(uid=Depends(user), body: dict = Body(...)):
    if not str(body.get("endpoint", "")).startswith("https://"):
        _err("bad subscription")
    return {"devices": notify.subscribe(uid, body)}


@app.post("/api/push/unsubscribe")
def push_unsubscribe(uid=Depends(user), body: dict = Body(...)):
    notify.unsubscribe(uid, body.get("endpoint", ""))
    return {"ok": True}


@app.post("/api/push/test")
def push_test(uid=Depends(user)):
    res = notify.send(uid, "jobkit test", "Notifications work. You'll hear from me when a strong match shows up.",
                      path="/#/")
    if not res:
        _err("No notification channel set up yet. Enable push on this device or add an ntfy topic.")
    return res


# ---- admin -----------------------------------------------------------------

@app.get("/api/admin")
def admin_view(uid=Depends(admin)):
    return {"users": auth.public_users(), "invites": auth.list_invites()[-30:], "env": config.env_status(),
            "meta": scraper.load_meta(), "ai_daily_limit": AI_DAILY_LIMIT}


@app.post("/api/admin/invite")
def admin_invite(uid=Depends(admin)):
    return {"code": auth.create_invite(uid)}


@app.delete("/api/admin/invites/{code}")
def admin_revoke_invite(code: str, uid=Depends(admin)):
    auth.revoke_invite(code)
    return {"ok": True}


@app.post("/api/admin/users/{target}/reset")
def admin_reset(target: str, uid=Depends(admin)):
    return {"code": auth.reset_user(target, uid)}


@app.delete("/api/admin/users/{target}")
def admin_delete(target: str, uid=Depends(admin)):
    if target == uid:
        _err("You can't delete yourself.")
    auth.delete_user(target)
    return {"ok": True}


# ---- PWA -------------------------------------------------------------------

@app.get("/sw.js")
def service_worker():
    return FileResponse(WEB / "sw.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
