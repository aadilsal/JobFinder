"""Pull a user's public GitHub repos (description, languages, topics, README excerpt) into
data/users/<uid>/github_projects.json so the CV tailoring can cite real projects.
Your include/exclude choices survive re-syncs."""
import json, os
import requests
import config

API = "https://api.github.com"


def _h(raw=False):
    h = {"Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
         "User-Agent": "jobkit"}
    if os.getenv("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.getenv('GITHUB_TOKEN')}"
    return h


def path(uid):
    return config.user_dir(uid) / "github_projects.json"


def load(uid):
    return json.loads(path(uid).read_text(encoding="utf-8")) if path(uid).exists() else []


def set_include(uid, name, include):
    repos = load(uid)
    for r in repos:
        if r["name"] == name:
            r["include"] = include
    path(uid).write_text(json.dumps(repos, indent=2), encoding="utf-8")


def sync(uid, user=None, limit=30):
    user = user or config.load(uid).get("github_user") or os.getenv("GITHUB_USER")
    if not user:
        raise ValueError("No GitHub username. Add your GitHub link to your profile or set it in Settings.")
    r = requests.get(f"{API}/users/{user}/repos", headers=_h(),
                     params={"per_page": 100, "sort": "pushed"}, timeout=25)
    if r.status_code in (403, 429):
        raise RuntimeError("GitHub rate limit hit. Add GITHUB_TOKEN to .env.local (github.com/settings/tokens, "
                           "no scopes needed for public repos) and retry.")
    r.raise_for_status()
    keep = {x["name"]: x.get("include", True) for x in load(uid)}
    repos = [x for x in r.json() if not x["fork"] and not x["archived"]][:limit]
    result = []
    for x in repos:
        name = x["name"]
        langs = requests.get(f"{API}/repos/{user}/{name}/languages", headers=_h(), timeout=25)
        rd = requests.get(f"{API}/repos/{user}/{name}/readme", headers=_h(raw=True), timeout=25)
        result.append({
            "id": f"gh:{name}", "name": name, "url": x["html_url"],
            "description": x.get("description") or "", "topics": x.get("topics", []),
            "languages": list(langs.json().keys())[:6] if langs.ok else [],
            "stars": x["stargazers_count"], "pushed": x["pushed_at"][:10],
            "readme_excerpt": rd.text[:1800] if rd.ok else "",
            "include": keep.get(name, True),
        })
    path(uid).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
