"""Build one application package for a user: tailored CV.pdf, Cover_Letter.pdf, email.txt, notes.md,
tailored.json in data/users/<uid>/out/<company>_<role>_<date>/ and a row in the tracker."""
import ipaddress, json, os, re, socket
from datetime import date
from urllib.parse import urlparse

import requests
import config, generator, render, scraper, tracker


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:40] or "job"


def _public_host(url):
    """Block server-side requests to localhost / private networks / cloud metadata (users paste these URLs)."""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        return False
    try:
        for info in socket.getaddrinfo(u.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def fetch_url(url):
    if not _public_host(url):
        raise ValueError("That URL can't be fetched. Paste the job description text instead.")
    r = requests.get(url, headers=scraper.HEADERS, timeout=25, allow_redirects=False)
    for _ in range(3):
        nxt = r.headers.get("location", "")
        if not r.is_redirect:
            break
        if not _public_host(nxt):
            raise ValueError("That URL redirects somewhere that can't be fetched.")
        r = requests.get(nxt, headers=scraper.HEADERS, timeout=25, allow_redirects=False)
    html = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", r.text)
    return re.sub(r"\s+", " ", scraper.strip_html(html)).strip()[:14000]


def folder(uid, name):
    """Resolve an application folder name safely inside the user's out/ dir."""
    base = config.out_dir(uid).resolve()
    p = (base / name).resolve()
    if p.parent != base or not p.is_dir():
        raise FileNotFoundError(name)
    return p


def _write_package(p, profile, c, theme):
    render.render_cv(profile, c, str(p / "CV.pdf"), theme)
    render.render_letter(profile, c, str(p / "Cover_Letter.pdf"), theme)
    (p / "email.txt").write_text(f"Subject: {c['email_subject']}\n\n{c['email_body']}\n", encoding="utf-8")
    (p / "tailored.json").write_text(json.dumps({**c, "theme": theme}, indent=1), encoding="utf-8")


def apply(uid, jd, company="", job=None, theme=None, log=print):
    profile, gh = generator.load_inputs(uid)
    theme = theme or config.load(uid).get("cv_theme", "classic")
    if job:
        jd = f"{job['title']} at {job['company']}\nLocation: {job['location']}\n\n{job['desc']}"
        company = company or job["company"]
    if os.getenv("ANTHROPIC_API_KEY"):
        c = generator.tailor(jd, profile, gh, company)
    else:
        log("! ANTHROPIC_API_KEY not set - generating the untailored base CV only.")
        c = generator.fallback(profile, job["title"] if job else "Software Engineer")
        c["company"] = company or c["company"]
    name = f"{slug(c.get('company') or company)}_{slug(c['role'])}_{date.today()}"
    p, n = config.out_dir(uid) / name, 2
    while p.exists():
        p, n = config.out_dir(uid) / f"{name}-{n}", n + 1
    p.mkdir(parents=True)
    _write_package(p, profile, c, theme)
    (p / "notes.md").write_text(
        f"# {c['role']} @ {c.get('company')}\n\nMatch score: {c['match_score']}/100\n\n"
        f"Matched keywords: {', '.join(c['keywords_matched'])}\n\nGaps / things to check:\n"
        + "".join(f"- {g}\n" for g in c["gaps"]) + "\n\n## Job description\n" + jd[:6000], encoding="utf-8")
    (p / "jd.txt").write_text(jd, encoding="utf-8")
    emails = extract_emails(jd)
    row = tracker.add(uid, company=c.get("company") or company, role=c["role"], match=c["match_score"],
                      folder=p.name, job_url=(job or {}).get("url", ""), job_key=(job or {}).get("key", ""),
                      contact_email=emails[0] if emails else "",
                      source=((job or {}).get("source") or "pasted").split("/")[0], theme=theme)
    if job:
        scraper.set_state(uid, job["key"], "applied")
    return p.name, c, row


def load_package(uid, name):
    p = folder(uid, name)
    c = json.loads((p / "tailored.json").read_text(encoding="utf-8"))
    jd = (p / "jd.txt").read_text(encoding="utf-8") if (p / "jd.txt").exists() else ""
    files = sorted(f.name for f in p.iterdir() if f.is_file())
    extra = {k: json.loads((p / f"{k}.json").read_text(encoding="utf-8"))
             for k in ("answers", "interview") if (p / f"{k}.json").exists()}
    return {"folder": name, "tailored": c, "jd": jd, "files": files, "emails": extract_emails(jd), **extra}


def save_extra(uid, name, kind, data):
    """Store generated form answers / interview prep next to the application."""
    (folder(uid, name) / f"{kind}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")


def download_name(profile, fname):
    """What recruiters see: 'Aadil Salman Butt CV.pdf', 'Aadil Salman Butt Cover Letter.pdf'."""
    person = re.sub(r"[^\w .'-]", "", profile.get("name") or "").strip() or "Candidate"
    return {"CV.pdf": f"{person} CV.pdf", "Cover_Letter.pdf": f"{person} Cover Letter.pdf"}.get(fname, fname)


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}")
_SKIP = ("noreply", "no-reply", "donotreply", "privacy", "unsubscribe", "abuse", "security@", "legal@",
         "example.", "sentry", "wixpress", "@email.com", "@domain.com", "dpo@", "gdpr")
_LIKELY = ("career", "jobs", "job@", "hr@", "hr.", "recruit", "talent", "hiring", "apply", "people", "cv@", "resume")


def extract_emails(text):
    """Addresses a candidate could send an application to, most likely first (hiring inboxes, then others)."""
    found = []
    for m in EMAIL_RE.findall(text or ""):
        e = m.strip(".").lower()
        if e not in found and not any(s in e for s in _SKIP) and not e.endswith((".png", ".jpg", ".gif")):
            found.append(e)
    return sorted(found, key=lambda e: (not any(w in e for w in _LIKELY), found.index(e)))


def rerender(uid, name, edits, theme=None):
    """Save your edits to the letter/email/summary/bullets and rebuild the PDFs."""
    p = folder(uid, name)
    c = json.loads((p / "tailored.json").read_text(encoding="utf-8"))
    allowed = {"headline", "summary", "cover_letter", "email_subject", "email_body", "experience", "projects", "skills"}
    c.update({k: v for k, v in edits.items() if k in allowed})
    profile, _ = generator.load_inputs(uid)
    c = generator.validate(c, profile)
    c["theme"] = theme or c.get("theme") or "classic"
    _write_package(p, profile, c, c["theme"])
    return c


def base_cv(uid, theme):
    """Untailored CV from the profile, for previewing the designs."""
    profile, _ = generator.load_inputs(uid)
    p = config.user_dir(uid) / f"base_cv_{theme}.pdf"
    render.render_cv(profile, generator.fallback(profile), str(p), theme)
    return p
