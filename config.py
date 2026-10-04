"""Shared paths, env loading and per-user settings (search keywords, sources, alerts).

Layout:
  data/                     shared: users.json, scraped jobs pool, VAPID keys
  data/users/<uid>/         per user: profile.json, config.json, jobs.json, ai_scores.json, out/ ...
"""
import json, os, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
USERS = DATA / "users"
USERS.mkdir(parents=True, exist_ok=True)

try:
    from dotenv import load_dotenv
    # .env.local wins over .env; neither overrides variables already set in the shell
    load_dotenv(ROOT / ".env.local")
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

DEFAULTS = {
    "search_terms": ["full stack", "node.js", "react", "next.js", "python", "ai engineer"],
    "title_keywords": ["full stack", "fullstack", "full-stack", "software engineer", "software developer",
                       "backend", "back-end", "frontend", "front-end", "web developer", "node", "react",
                       "next.js", "nextjs", "python", "typescript", "javascript", "ai engineer", "llm",
                       "automation", "ml engineer"],
    "skills": ["react", "next.js", "nextjs", "node", "express", "typescript", "javascript", "python",
               "fastapi", "django", "postgres", "mysql", "mongodb", "redis", "kafka", "docker",
               "kubernetes", "aws", "rest", "langchain", "rag", "llm", "openai", "n8n", "stripe",
               "tailwind", "ci/cd", "microservices"],
    "too_senior": ["senior", "sr.", "staff", "principal", "lead", "head of", "director", "architect",
                   "manager", "5+ years", "6+ years", "7+ years", "8+ years", "10+ years"],
    "bad_title": ["intern", "sales", "marketing", "designer", "recruiter", "support", "data entry",
                  "java ", "php", ".net", "ruby", "golang", "android", "ios", "devops engineer"],
    "open_locations": ["worldwide", "anywhere", "global", "asia", "apac", "pakistan", "lahore", "emea", "remote"],
    "closed_locations": ["us only", "usa only", "united states only", "u.s. only", "canada only", "uk only",
                         "must be located in the us", "us citizens", "eu only", "europe only",
                         "north america", "latam only", "us-based", "us based"],
    "min_score": 20,
    "max_age_days": 30,
    # Watcher: scrape on a timer, have Claude score the best new jobs, alert your phone on strong matches
    "scrape_every_hours": 6,
    "alert_threshold": 90,          # AI match % that triggers a phone notification
    "ai_prefilter_score": 45,       # only keyword-score >= this gets sent to Claude (keeps cost low)
    "ai_score_top_n": 25,           # max jobs AI-scored per run, per user
    "heuristic_alert_score": 80,    # used for alerts only when ANTHROPIC_API_KEY is missing
    "daily_digest": True,           # one morning notification with the day's best jobs
    "digest_hour_utc": 4,           # 4 UTC = 9 am Pakistan time
    "watch_companies": [],          # companies you liked/shortlisted: their new roles get a boost and an alert
    "cv_theme": "classic",
    "github_user": "",
    "ntfy_topic": "",
    "telegram_chat_id": "",
    "sources": {
        "remotive": True, "remoteok": True, "arbeitnow": True, "himalayas": True, "jobicy": True,
        "weworkremotely": True, "workingnomads": True, "hackernews": True, "greenhouse": True,
        "lever": True, "ashby": True, "linkedin": True, "adzuna": True, "jsearch": True, "jobspy": True,
    },
    # Public ATS job boards - add the slug from the company's careers URL
    # boards.greenhouse.io/<slug> | jobs.lever.co/<slug> | jobs.ashbyhq.com/<slug>
    "ats_companies": {
        "greenhouse": ["gitlab", "cloudflare", "mongodb", "elastic", "vercel", "grafanalabs", "twilio", "airtable"],
        "lever": ["spotify", "plaid", "binance", "toptal"],
        "ashby": ["supabase", "linear", "posthog", "ramp", "deel", "replit", "langchain", "n8n"],
    },
    "linkedin": {"locations": ["Worldwide", "Pakistan"], "pages": 2, "past_seconds": 604800, "max_details": 60},
    "adzuna_countries": ["gb", "us", "in"],
    "jsearch_queries": ["full stack developer remote", "node.js developer remote", "python developer remote"],
    "jobspy": {"sites": ["indeed", "glassdoor", "google", "zip_recruiter"], "locations": ["Remote", "Lahore, Pakistan"],
               "country_indeed": "Pakistan", "results_wanted": 30, "hours_old": 168},
}


def valid_uid(uid):
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9_-]{2,31}", uid or ""))


def user_dir(uid):
    if not valid_uid(uid):
        raise ValueError(f"bad user id: {uid!r}")
    d = USERS / uid
    (d / "out").mkdir(parents=True, exist_ok=True)
    return d


def out_dir(uid):
    return user_dir(uid) / "out"


def profile_path(uid):
    return user_dir(uid) / "profile.json"


def load(uid=None):
    cfg = json.loads(json.dumps(DEFAULTS))
    f = user_dir(uid) / "config.json" if uid else None
    if f and f.exists():
        for k, v in json.loads(f.read_text(encoding="utf-8")).items():
            cfg[k] = {**cfg[k], **v} if isinstance(v, dict) and isinstance(cfg.get(k), dict) else v
    return cfg


def save(uid, cfg):
    (user_dir(uid) / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def merged(cfgs):
    """One scrape serves every user: union of everyone's search terms, sources and companies."""
    out = json.loads(json.dumps(DEFAULTS))
    if not cfgs:
        return out
    uniq = lambda xs: list(dict.fromkeys(x for x in xs if x))
    for k in ("search_terms", "title_keywords", "bad_title", "jsearch_queries", "adzuna_countries"):
        out[k] = uniq(x for c in cfgs for x in c[k])
    # a bad_title word only filters during the shared scrape if nobody wants it
    out["bad_title"] = [b for b in out["bad_title"] if all(b in c["bad_title"] for c in cfgs)]
    out["sources"] = {s: any(c["sources"].get(s) for c in cfgs) for s in out["sources"]}
    out["ats_companies"] = {a: uniq(x for c in cfgs for x in c["ats_companies"].get(a, [])) for a in out["ats_companies"]}
    out["linkedin"]["locations"] = uniq(x for c in cfgs for x in c["linkedin"]["locations"])
    out["jobspy"]["locations"] = uniq(x for c in cfgs for x in c["jobspy"]["locations"])
    out["max_age_days"] = max(c["max_age_days"] for c in cfgs)
    return out


def env_status():
    keys = ["ANTHROPIC_API_KEY", "GITHUB_TOKEN", "JOBKIT_MODEL", "PUBLIC_URL",
            "ADZUNA_APP_ID", "ADZUNA_APP_KEY", "RAPIDAPI_KEY", "NTFY_SERVER", "TELEGRAM_BOT_TOKEN"]
    return {k: bool(os.getenv(k)) for k in keys}
