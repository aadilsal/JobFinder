"""Scrape job listings from many sources once (data/jobs_raw.json), then rank them per user
against their profile (data/users/<uid>/jobs.json + jobs.csv).

Sources (each user toggles them on the Settings page):
  Remote boards : Remotive, RemoteOK, Arbeitnow, Himalayas, Jobicy, We Work Remotely, Working Nomads
  Community     : Hacker News "Who is hiring?" (latest monthly thread)
  Company ATS   : Greenhouse, Lever and Ashby public boards for the companies listed in config.json
  Aggregators   : LinkedIn public guest listings (no login)
                  Adzuna            - needs ADZUNA_APP_ID + ADZUNA_APP_KEY (free, developer.adzuna.com)
                  JSearch           - needs RAPIDAPI_KEY (Google for Jobs: LinkedIn/Indeed/Glassdoor/ZipRecruiter...)
                  JobSpy            - needs `pip install python-jobspy` (Indeed/Glassdoor/Google/ZipRecruiter)

Run:   python cli.py scrape        (or "Scrape now" in the web app)
Always-on: the server runs watcher.py on a timer
"""
import csv, hashlib, html, json, os, re, sys, time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests
import config

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
RAW_FILE = config.DATA / "jobs_raw.json"        # shared deduped pool from the last scrape
META_FILE = config.DATA / "scrape_meta.json"    # last run time + per-source counts
# per user (data/users/<uid>/): jobs.json, jobs.csv, seen_jobs.json, job_state.json (shortlisted/hidden/applied)


class Skip(Exception):
    """Raised by a source that is not configured (missing key or package)."""


# ---- helpers ---------------------------------------------------------------

def strip_html(s):
    s = html.unescape(s or "")
    s = re.sub(r'(?i)href=["\']mailto:([^"\'?]+)[^>]*>', r'> \1 ', s)   # keep "apply by email" addresses
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>", "\n", s)
    return re.sub(r"[ \t\r\f\v]+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def norm_date(v):
    if v in (None, ""):
        return ""
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000 if v > 1e11 else v, timezone.utc).date().isoformat()
    s = str(v).strip()
    if m := re.match(r"\d{4}-\d{2}-\d{2}", s):
        return m.group()
    try:
        return parsedate_to_datetime(s).date().isoformat()
    except Exception:
        return ""


def _s(v):
    """Clean a value that may be None/NaN (JobSpy returns pandas NaN)."""
    return "" if v is None or v != v else str(v)


def get(url, quiet=False, headers=None, **kw):
    try:
        r = requests.get(url, headers={**HEADERS, **(headers or {})}, timeout=25, **kw)
        r.raise_for_status()
        return r
    except Exception as e:
        if not quiet:
            print(f"  ! {url[:70]} failed: {e}", file=sys.stderr)
        return None


def job(source, title, company, location, url, desc, posted=""):
    return dict(source=source, title=_s(title).strip(), company=_s(company).strip(),
                location=_s(location).strip(), url=_s(url), desc=strip_html(_s(desc))[:6000],
                date=norm_date(posted))


def _pmap(fn, items, workers=6):
    out = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for res in ex.map(fn, items):
            out += res
    return out


def title_ok(title, cfg):
    t = title.lower()
    return not any(b in t for b in cfg["bad_title"]) and any(k in t for k in cfg["title_keywords"])


# ---- remote job boards -----------------------------------------------------

def remotive(cfg):
    out = []
    for q in cfg["search_terms"]:
        r = get("https://remotive.com/api/remote-jobs", params={"category": "software-dev", "search": q})
        for j in (r.json().get("jobs", []) if r else []):
            out.append(job("Remotive", j["title"], j["company_name"], j.get("candidate_required_location"),
                           j["url"], j.get("description"), j.get("publication_date")))
    return out


def remoteok(cfg):
    r = get("https://remoteok.com/api")
    data = [j for j in (r.json() if r else []) if isinstance(j, dict) and j.get("position")]
    return [job("RemoteOK", j["position"], j.get("company"), j.get("location"), j.get("url"),
                j.get("description"), j.get("date")) for j in data]


def arbeitnow(cfg):
    out = []
    for p in range(1, 6):
        r = get("https://www.arbeitnow.com/api/job-board-api", params={"page": p})
        data = r.json().get("data", []) if r else []
        if not data:
            break
        out += [job("Arbeitnow", j["title"], j["company_name"], j.get("location"), j["url"],
                    j.get("description"), j.get("created_at")) for j in data if j.get("remote")]
    return out


def himalayas(cfg):
    out, offset = [], 0
    while offset < 400:
        r = get("https://himalayas.app/jobs/api", params={"limit": 20, "offset": offset})
        data = r.json().get("jobs", []) if r else []
        if not data:
            break
        for j in data:
            locs = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
            out.append(job("Himalayas", j.get("title"), j.get("companyName"), locs,
                           j.get("applicationLink") or j.get("guid"), j.get("description") or j.get("excerpt"),
                           j.get("pubDate")))
        offset += len(data)
    return out


def jobicy(cfg):
    out = []
    for params in ({"count": 100}, {"count": 100, "industry": "dev"}):
        r = get("https://jobicy.com/api/v2/remote-jobs", params=params)
        out += [job("Jobicy", j.get("jobTitle"), j.get("companyName"), j.get("jobGeo"), j.get("url"),
                    j.get("jobDescription"), j.get("pubDate")) for j in (r.json().get("jobs", []) if r else [])]
    return out


def weworkremotely(cfg):
    out = []
    feeds = ["remote-jobs.rss", "categories/remote-full-stack-programming-jobs.rss",
             "categories/remote-back-end-programming-jobs.rss", "categories/remote-front-end-programming-jobs.rss"]
    for feed in feeds:
        r = get(f"https://weworkremotely.com/{feed}")
        if not r:
            continue
        try:
            for it in ET.fromstring(r.content).iter("item"):
                title = it.findtext("title", "")
                company, _, t = title.partition(": ")
                out.append(job("WWR", t or title, company if t else "", it.findtext("region", ""),
                               it.findtext("link", ""), it.findtext("description", ""), it.findtext("pubDate")))
        except ET.ParseError:
            pass
    return out


def workingnomads(cfg):
    r = get("https://www.workingnomads.com/api/exposed_jobs/")
    return [job("WorkingNomads", j.get("title"), j.get("company_name"), j.get("location"), j.get("url"),
                j.get("description"), j.get("pub_date")) for j in (r.json() if r else [])]


# ---- community -------------------------------------------------------------

def hackernews(cfg):
    r = get("https://hn.algolia.com/api/v1/search_by_date",
            params={"tags": "story,author_whoishiring", "hitsPerPage": 10})
    hits = [h for h in (r.json().get("hits", []) if r else []) if "who is hiring" in h.get("title", "").lower()]
    if not hits:
        return []
    item = get(f"https://hn.algolia.com/api/v1/items/{hits[0]['objectID']}")
    out = []
    for c in (item.json().get("children", []) if item else []):
        text = c.get("text") or ""
        first = strip_html(html.unescape(text).split("<p>")[0])
        if "|" not in first:
            continue
        parts = [p.strip() for p in first.split("|")]
        role = next((p for p in parts[1:] if any(k in p.lower() for k in cfg["title_keywords"])),
                    " | ".join(parts[1:3]))
        out.append(job("HN Hiring", role, parts[0][:60], first[:200],
                       f"https://news.ycombinator.com/item?id={c['id']}", text, c.get("created_at")))
    return out


# ---- company ATS boards ----------------------------------------------------

def greenhouse(cfg):
    def one(slug):
        r = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", quiet=True, params={"content": "true"})
        return [job("Greenhouse", j["title"], slug.title(), (j.get("location") or {}).get("name"),
                    j["absolute_url"], j.get("content"), j.get("updated_at"))
                for j in (r.json().get("jobs", []) if r else [])]
    return _pmap(one, cfg["ats_companies"].get("greenhouse", []))


def lever(cfg):
    def one(slug):
        r = get(f"https://api.lever.co/v0/postings/{slug}", quiet=True, params={"mode": "json"})
        return [job("Lever", j.get("text"), slug.title(),
                    " ".join(filter(None, [(j.get("categories") or {}).get("location"), j.get("workplaceType")])),
                    j.get("hostedUrl"), j.get("descriptionPlain") or j.get("description"), j.get("createdAt"))
                for j in (r.json() if r else [])]
    return _pmap(one, cfg["ats_companies"].get("lever", []))


def ashby(cfg):
    def one(slug):
        r = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", quiet=True)
        return [job("Ashby", j.get("title"), slug.title(),
                    (j.get("location") or "") + (" Remote" if j.get("isRemote") else ""),
                    j.get("jobUrl"), j.get("descriptionPlain") or j.get("descriptionHtml"), j.get("publishedAt"))
                for j in (r.json().get("jobs", []) if r else [])]
    return _pmap(one, cfg["ats_companies"].get("ashby", []))


# ---- aggregators -----------------------------------------------------------

def _rx(pattern, text):
    m = re.search(pattern, text, re.S)
    return strip_html(m.group(1)) if m else ""


def linkedin(cfg):
    """Public guest job search (what logged-out visitors see). Kept slow and capped to stay polite."""
    li = cfg["linkedin"]
    base = "https://www.linkedin.com/jobs-guest/jobs/api"
    cards = {}
    for term in cfg["search_terms"]:
        for loc in li["locations"]:
            for page in range(li["pages"]):
                params = {"keywords": term, "location": loc, "f_TPR": f"r{li['past_seconds']}", "start": page * 25}
                if loc.lower() in ("worldwide", "remote"):
                    params["f_WT"] = "2"   # remote only
                r = get(f"{base}/seeMoreJobPostings/search", quiet=True, params=params)
                if not r or not r.text.strip():
                    break
                for block in r.text.split("<li")[1:]:
                    jid = re.search(r"jobPosting:(\d+)", block)
                    posted = re.search(r'datetime="([\d-]+)"', block)
                    if jid:
                        cards[jid.group(1)] = dict(
                            title=_rx(r'base-search-card__title[^>]*>(.*?)</h3>', block),
                            company=_rx(r'base-search-card__subtitle[^>]*>(.*?)</h4>', block),
                            location=_rx(r'job-search-card__location[^>]*>(.*?)</span>', block),
                            date=posted.group(1) if posted else "")
                time.sleep(1)
    out, details = [], 0
    for jid, c in cards.items():
        desc = ""
        if title_ok(c["title"], cfg) and details < li["max_details"]:
            r = get(f"{base}/jobPosting/{jid}", quiet=True)
            desc = _rx(r'show-more-less-html__markup[^>]*>(.*?)</div>', r.text) if r else ""
            details += 1
            time.sleep(0.5)
        out.append(job("LinkedIn", c["title"], c["company"], c["location"],
                       f"https://www.linkedin.com/jobs/view/{jid}", desc, c["date"]))
    return out


def adzuna(cfg):
    app_id, key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not (app_id and key):
        raise Skip("set ADZUNA_APP_ID and ADZUNA_APP_KEY")
    out = []
    for country in cfg["adzuna_countries"]:
        for term in cfg["search_terms"]:
            r = get(f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
                    params={"app_id": app_id, "app_key": key, "what": term, "results_per_page": 50,
                            "max_days_old": cfg["max_age_days"]})
            out += [job("Adzuna", j.get("title"), (j.get("company") or {}).get("display_name"),
                        (j.get("location") or {}).get("display_name"), j.get("redirect_url"),
                        j.get("description"), j.get("created")) for j in (r.json().get("results", []) if r else [])]
    return out


def jsearch(cfg):
    key = os.getenv("RAPIDAPI_KEY")
    if not key:
        raise Skip("set RAPIDAPI_KEY")
    out = []
    for q in cfg["jsearch_queries"]:
        r = get("https://jsearch.p.rapidapi.com/search",
                headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
                params={"query": q, "page": 1, "num_pages": 2, "date_posted": "week"})
        for j in (r.json().get("data", []) if r else []):
            loc = ", ".join(filter(None, [j.get("job_city"), j.get("job_country")]))
            out.append(job(f"JSearch/{j.get('job_publisher') or '?'}", j.get("job_title"), j.get("employer_name"),
                           ("Remote " if j.get("job_is_remote") else "") + loc, j.get("job_apply_link"),
                           j.get("job_description"), j.get("job_posted_at_datetime_utc")))
    return out


def jobspy(cfg):
    try:
        from jobspy import scrape_jobs
    except ImportError:
        raise Skip("pip install python-jobspy")
    js, out = cfg["jobspy"], []
    for term in cfg["search_terms"]:
        for loc in js["locations"]:
            try:
                df = scrape_jobs(site_name=js["sites"], search_term=term, location=loc,
                                 results_wanted=js["results_wanted"], hours_old=js["hours_old"],
                                 country_indeed=js["country_indeed"], is_remote=loc.lower() == "remote")
            except Exception as e:
                print(f"  ! jobspy '{term}' @ {loc}: {e}", file=sys.stderr)
                continue
            out += [job(f"JobSpy/{_s(j.get('site'))}", j.get("title"), j.get("company"), j.get("location"),
                        j.get("job_url"), j.get("description"), _s(j.get("date_posted")))
                    for j in df.to_dict("records")]
    return out


SOURCES = {f.__name__: f for f in [remotive, remoteok, arbeitnow, himalayas, jobicy, weworkremotely, workingnomads,
                                    hackernews, greenhouse, lever, ashby, linkedin, adzuna, jsearch, jobspy]}


# ---- scoring + pipeline ----------------------------------------------------

def score(j, cfg):
    t, loc = j["title"].lower(), j["location"].lower()
    text = f"{t} {j['desc'].lower()}"
    if not title_ok(j["title"], cfg):
        return -1, ""
    s, notes = 25, []
    hits = sorted({k for k in cfg["skills"] if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", text)})
    s += min(len(hits), 10) * 5
    if any(x in t or x in text[:1500] for x in cfg["too_senior"]):
        s -= 25; notes.append("senior?")
    open_words = [o for o in cfg["open_locations"] if o != "remote"]
    plain_remote = re.fullmatch(r"\W*(100%|fully)?\s*remote\W*", loc) is not None
    if any(c in loc or c in text[:2000] for c in cfg["closed_locations"]):
        s -= 40; notes.append("region-locked")
    elif not loc or plain_remote or any(o in loc for o in open_words):
        s += 10
    else:                       # names a country/city you didn't list, e.g. "Remote - US", "Hybrid - Dublin"
        s -= 30; notes.append("location?")
    if any(w in t for w in ["junior", "associate", "entry", "graduate", "mid"]):
        s += 10
    if not j["desc"]:
        notes.append("no description")
    return s, ", ".join(hits[:8]) + (f" | {' '.join(notes)}" if notes else "")


def _read(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _user_file(uid, name):
    return config.user_dir(uid) / name


def load_jobs(uid):
    return _read(_user_file(uid, "jobs.json"), [])


def load_meta():
    return _read(META_FILE, {})


def load_state(uid):
    return _read(_user_file(uid, "job_state.json"), {})


def set_state(uid, key, status):
    state = load_state(uid)
    if status:
        state[key] = status
    else:
        state.pop(key, None)
    _user_file(uid, "job_state.json").write_text(json.dumps(state, indent=1), encoding="utf-8")


def fetch(cfg=None, only=None, log=print):
    """Hit every enabled source once (shared by all users), dedupe, save data/jobs_raw.json."""
    cfg = cfg or config.load()
    enabled = [n for n, on in cfg["sources"].items() if on and n in SOURCES and (not only or n in only)]
    raw, stats = [], {}
    log(f"Scraping {len(enabled)} sources: {', '.join(enabled)}")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(SOURCES[n], cfg): n for n in enabled}
        for f in as_completed(futs):
            n = futs[f]
            try:
                got = f.result()
                raw += got
                stats[n] = {"fetched": len(got), "status": "ok"}
            except Skip as e:
                stats[n] = {"fetched": 0, "status": f"skipped: {e}"}
            except Exception as e:
                stats[n] = {"fetched": 0, "status": f"error: {e}"}
            log(f"  {n:<15} {stats[n]['fetched']:>5} jobs  {stats[n]['status']}")

    # dedupe on URL and on title+company (the same job is often on several boards)
    cutoff = (date.today() - timedelta(days=cfg["max_age_days"])).isoformat()
    uniq, seen_tc = {}, set()
    for j in raw:
        if not j["title"] or (j["date"] and j["date"] < cutoff):
            continue
        tc = re.sub(r"[^a-z0-9]", "", f"{j['title']}|{j['company']}".lower())
        if tc in seen_tc:
            continue
        seen_tc.add(tc)
        k = j["url"] or tc
        if k not in uniq:
            uniq[k] = {**j, "key": hashlib.md5(k.encode()).hexdigest()[:10]}
    pool = list(uniq.values())
    RAW_FILE.write_text(json.dumps(pool), encoding="utf-8")
    META_FILE.write_text(json.dumps({"last_run": datetime.now().isoformat(timespec="seconds"), "fetched": len(raw),
                                     "unique": len(pool), "sources": stats}, indent=1), encoding="utf-8")
    log(f"{len(raw)} fetched, {len(pool)} unique")
    return pool


def rank(pool, cfg, uid, log=print):
    """Score the shared pool with one user's keywords; save data/users/<uid>/jobs.json (+ jobs.csv)."""
    seen_file = _user_file(uid, "seen_jobs.json")
    seen = set(_read(seen_file, []))
    rows = []
    for j in pool:
        s, why = score(j, cfg)
        if s >= cfg["min_score"]:
            rows.append({**j, "score": s, "why": why, "new": j["key"] not in seen})
    rows.sort(key=lambda r: (r["new"], r["score"], r["date"]), reverse=True)
    for i, r in enumerate(rows, 1):
        r["id"] = i
    _user_file(uid, "jobs.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    with open(_user_file(uid, "jobs.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "new", "score", "title", "company", "location", "source", "date", "matched", "url"])
        for r in rows:
            w.writerow([r["id"], r["new"], r["score"], r["title"], r["company"], r["location"],
                        r["source"], r["date"], r["why"], r["url"]])
    seen_file.write_text(json.dumps(sorted(seen | {r["key"] for r in rows})), encoding="utf-8")
    log(f"[{uid}] {len(rows)} matched ({sum(r['new'] for r in rows)} new)")
    return rows


def run(uid, cfg=None, only=None, log=print):
    """Fetch + rank for a single user (CLI convenience)."""
    cfg = cfg or config.load(uid)
    return rank(fetch(cfg, only, log), cfg, uid, log)
