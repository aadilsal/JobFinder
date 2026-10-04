"""Tailor CV, cover letter, application email and recruiter outreach to a job using Claude.
Facts come ONLY from profile.json and github_projects.json - the model selects, orders and rewords."""
import json, os, re
import config

MODEL = os.getenv("JOBKIT_MODEL", "claude-sonnet-5-5")

SYSTEM = """You tailor job applications for one candidate. Hard rules:
1. Use ONLY facts present in the candidate PROFILE and GITHUB PROJECTS provided. Never invent employers, titles, dates, metrics, tools, certifications or years of experience.
2. You may select, reorder, merge and reword bullets to match the job description (mirror its terminology when the candidate truly has that skill). Keep every number exactly as given.
3. If the job requires something the candidate lacks, do NOT claim it. List it under "gaps". Never claim a skill in the skills section that is not in the profile.
4. For GitHub projects, only describe what the repo description, topics, languages and README excerpt support. No made-up metrics. Prefer a profile project over its GitHub duplicate.
5. CV must fit one page: summary 2-3 sentences; max 4 bullets for the main role, 2 for others; 2-4 projects with 1-3 bullets each; skills grouped in 4-6 rows, most relevant first.
6. Plain text only. No markdown, no emojis, no em dashes. Natural, specific, non-generic tone; no filler like "I am excited to apply" or "passionate".
7. Cover letter: 3-4 short paragraphs (under 280 words), addressed to the hiring team, tied to concrete evidence from the candidate's work and to the company/role. Do not invent facts about the company beyond what the JD states.
8. Email: short (under 120 words) body to accompany the attached CV and letter; subject line includes the role title and candidate name.
Return ONLY a JSON object, no prose."""

SCHEMA = """{
 "company": "string or Unknown",
 "role": "string",
 "match_score": 0-100,
 "headline": "e.g. Full Stack Engineer | React, Node.js, AI",
 "summary": "string",
 "skills": [{"label": "string", "items": ["string"]}],
 "experience": [{"id": "profile experience id", "bullets": ["string"]}],
 "projects": [{"id": "profile project id or gh:repo", "name": "string", "tech": "string", "url": "optional string", "bullets": ["string"]}],
 "cover_letter": "paragraphs separated by blank lines",
 "email_subject": "string",
 "email_body": "string",
 "keywords_matched": ["string"],
 "gaps": ["string"]
}"""

OUTREACH = {
    "cold_email": "Cold email to a recruiter or hiring manager about this role, before or right after applying. Under 150 words. Open with why this role specifically, give 2 concrete proof points, end with a low-friction ask (a 15 minute call or pointer to the right person).",
    "linkedin_note": "LinkedIn connection request note. HARD LIMIT 280 characters including spaces. No subject. One proof point, one ask.",
    "linkedin_message": "LinkedIn direct message to a recruiter. Under 110 words. Mention the role, 2 proof points, ask whether they are the right person to speak with.",
    "referral_ask": "Message to an engineer who works at the company asking for a referral or a quick chat about the team. Under 110 words. Respectful of their time, no pressure, include the job link placeholder [job link].",
    "follow_up": "Follow-up email about 7 days after applying with no response. Under 90 words. Subject starts with 'Following up:'. Add one new piece of evidence not in the original application if possible.",
    "thank_you": "Thank-you email within 24 hours after an interview. Under 120 words. Reference [topic discussed] as a placeholder the candidate fills in, restate fit briefly.",
}

OUTREACH_SYSTEM = """You write short job-search outreach messages for one candidate.
Use ONLY facts from the candidate PROFILE and GITHUB PROJECTS. Never invent experience, metrics, mutual connections or facts about the company beyond the job description.
Plain text, no markdown, no emojis, no em dashes. Sound like a sharp engineer writing to a busy person: specific, warm, brief. No "I hope this finds you well", no "passionate", no "excited".
If the recipient name is unknown, use "Hi there" (or "Hi [Name]" for LinkedIn). Sign off with the candidate's first name plus their portfolio or LinkedIn link.
Return ONLY a JSON object: {"subject": "string, empty for LinkedIn notes", "body": "string"}"""


PROFILE_SCHEMA = """{
 "name": "", "headline": "e.g. Full Stack Engineer | React, Node.js, AI", "location": "City, Country",
 "email": "", "phone": "", "links": {"LinkedIn": "", "GitHub": "", "Portfolio": ""},
 "years_experience_text": "e.g. 3+ years of professional experience",
 "base_summary": "2-3 sentences",
 "target_roles": ["job titles this person is likely targeting"],
 "work_preferences": "where they can work, only if stated (remote, countries, relocation)",
 "skills": {"Group name": ["skill"]},
 "experience": [{"id": "short-slug", "company": "", "title": "", "location": "", "dates": "Mon YYYY - Mon YYYY or Present", "bullets": [""]}],
 "projects": [{"id": "short-slug", "name": "", "tech": "comma separated", "url": "", "bullets": [""]}],
 "education": [{"school": "", "degree": "", "dates": ""}],
 "certifications": [""]
}"""

PARSE_SYSTEM = """You convert a CV into structured JSON. Extract ONLY what the CV states; use "" or [] for anything missing - never guess contact details, dates, links or numbers.
Keep bullets close to the original wording and keep every metric exactly. Group skills into 4-8 sensible groups.
base_summary: use the CV's summary; if there is none, write 2 factual sentences strictly from the CV.
target_roles: infer 2-4 realistic titles from the most recent roles and skills.
Return ONLY the JSON object."""


def load_inputs(uid):
    profile = json.loads(config.profile_path(uid).read_text(encoding="utf-8"))
    gh_path = config.user_dir(uid) / "github_projects.json"
    gh = json.loads(gh_path.read_text(encoding="utf-8")) if gh_path.exists() else []
    return profile, [r for r in gh if r.get("include", True)]


def _extract_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    return json.loads(text[text.index("{"): text.rindex("}") + 1])


def _ask(system, prompt, max_tokens):
    import anthropic
    content = prompt if isinstance(prompt, list) else [{"type": "text", "text": prompt}]
    msg = anthropic.Anthropic().messages.create(model=MODEL, max_tokens=max_tokens, system=system,
                                                messages=[{"role": "user", "content": content}])
    return _extract_json("".join(b.text for b in msg.content if b.type == "text"))


# ---- onboarding: CV -> profile -> questions for whatever is missing ----------

def cv_text(data, filename):
    """Plain text from a DOCX/TXT/MD upload (PDFs go straight to Claude)."""
    if filename.lower().endswith(".docx"):
        import io, zipfile
        xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8", "ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        return re.sub(r"[ \t]+", " ", re.sub(r"<[^>]+>", "", xml)).strip()
    return data.decode("utf-8", "ignore")


def parse_cv(data, filename):
    import base64
    if filename.lower().endswith(".pdf"):
        content = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                   "data": base64.b64encode(data).decode()}},
                   {"type": "text", "text": f"Convert this CV to JSON matching:\n{PROFILE_SCHEMA}"}]
    else:
        content = f"<cv>\n{cv_text(data, filename)[:30000]}\n</cv>\n\nConvert this CV to JSON matching:\n{PROFILE_SCHEMA}"
    p = _ask(PARSE_SYSTEM, content, 6000)
    return normalize_profile(p)


def normalize_profile(p):
    blank = json.loads(PROFILE_SCHEMA.replace('"Group name": ["skill"]', ""))
    out = {**{k: ([] if isinstance(v, list) else {} if isinstance(v, dict) else "") for k, v in blank.items()}, **p}
    out["links"] = {k: v for k, v in (out.get("links") or {}).items() if v} or {}
    for i, e in enumerate(out["experience"]):
        e["id"] = re.sub(r"[^a-z0-9]+", "-", (e.get("id") or e.get("company") or f"exp{i}").lower()).strip("-") or f"exp{i}"
        e.setdefault("bullets", [])
    for i, pr in enumerate(out["projects"]):
        pr["id"] = re.sub(r"[^a-z0-9]+", "-", (pr.get("id") or pr.get("name") or f"proj{i}").lower()).strip("-") or f"proj{i}"
        pr.setdefault("bullets", []); pr.setdefault("tech", "")
    out["skills"] = {k: v for k, v in (out.get("skills") or {}).items() if v}
    out["certifications"] = [c for c in out.get("certifications", []) if c]
    return out


def profile_gaps(p):
    """Questions to ask during onboarding. required=False ones are nice-to-have."""
    q = []
    ask = lambda key, label, kind="text", required=True: q.append(
        {"key": key, "label": label, "kind": kind, "required": required})
    for key, label in [("name", "Your full name"), ("email", "Email recruiters should use"),
                       ("phone", "Phone number with country code"), ("location", "Where you live (City, Country)")]:
        if not p.get(key):
            ask(key, label)
    if not p.get("links", {}).get("LinkedIn"):
        ask("links.LinkedIn", "LinkedIn profile URL", required=False)
    if not p.get("links", {}).get("GitHub"):
        ask("links.GitHub", "GitHub profile URL (used to pull your projects)", required=False)
    if not p.get("links", {}).get("Portfolio"):
        ask("links.Portfolio", "Portfolio / personal site URL", required=False)
    if not p.get("years_experience_text"):
        ask("years_experience_text", "How much professional experience do you have? (e.g. 2+ years)")
    if not p.get("target_roles"):
        ask("target_roles", "Which job titles do you want? (comma separated)", "list")
    if not p.get("work_preferences"):
        ask("work_preferences", "Where can you work? (e.g. remote worldwide, onsite in Lahore, open to relocation)")
    if not p.get("skills"):
        ask("skills", "Your main skills (comma separated)", "list")
    if not p.get("base_summary"):
        ask("base_summary", "2-3 sentence professional summary", "textarea")
    if not p.get("experience") and not p.get("projects"):
        ask("experience.new", "Describe your most recent role: title, company, dates, then one achievement per line",
            "lines")
    for e in p.get("experience", []):
        if not e.get("bullets") and e.get("include", True):
            ask(f"experience.{e['id']}.bullets", f"What did you achieve as {e.get('title')} at {e.get('company')}? "
                                                 f"One per line, with numbers where you have them", "lines")
    if not p.get("education"):
        ask("education", "Highest degree, school and dates (e.g. BS Computer Science, FAST-NUCES, 2022-2026)",
            required=False)
    return q


def apply_answers(p, answers):
    p = json.loads(json.dumps(p))
    for key, val in answers.items():
        val = val.strip() if isinstance(val, str) else val
        if not val:
            continue
        lines = [l.strip(" -•\t") for l in str(val).splitlines() if l.strip(" -•\t")]
        if key.startswith("links."):
            p.setdefault("links", {})[key[6:]] = val
        elif key == "target_roles":
            p["target_roles"] = [x.strip() for x in val.split(",") if x.strip()]
        elif key == "skills":
            p["skills"] = {"Skills": [x.strip() for x in val.split(",") if x.strip()]}
        elif key == "education":
            p["education"] = [{"degree": val, "school": "", "dates": ""}]
        elif key == "experience.new":
            head = [x.strip() for x in lines[0].split(",")] + ["", "", ""]
            p.setdefault("experience", []).append({"id": "recent", "title": head[0], "company": head[1],
                                                   "location": "", "dates": head[2], "bullets": lines[1:]})
        elif key.startswith("experience.") and key.endswith(".bullets"):
            eid = key[len("experience."):-len(".bullets")]
            for e in p.get("experience", []):
                if e["id"] == eid:
                    e["bullets"] = lines
        else:
            p[key] = val
    return p


SUGGEST_SYSTEM = """You help a job seeker set up their job search. From their profile ONLY, suggest:
- target_roles: 3-5 realistic job titles they would get interviews for now (match their seniority; mix their strongest stack and adjacent titles).
- headline: one line like "Full Stack Engineer | React, Node.js, Python, AI" using only skills they have.
- years_experience_text: a SHORT phrase (max 7 words) like "1.5+ years of professional experience", computed from the role dates up to today (internships doing real engineering work count). Round down, never inflate.
- work_preferences: where they can likely work, e.g. "Remote worldwide, or onsite in Lahore". Base it on their location; never claim visas or relocation.
Return ONLY JSON: {"target_roles": [""], "headline": "", "years_experience_text": "", "work_preferences": ""}"""

SUGGESTABLE = ("target_roles", "headline", "years_experience_text", "work_preferences")


def suggest_fields(p):
    """AI suggestions for the job-search fields people usually leave blank. Falls back to simple rules."""
    if os.getenv("ANTHROPIC_API_KEY"):
        small = {k: p.get(k) for k in ("location", "base_summary", "skills", "experience", "projects", "education")}
        out = _ask(SUGGEST_SYSTEM, f"<profile>\n{json.dumps(small)}\n</profile>", 800)
        out["target_roles"] = [r for r in out.get("target_roles", []) if r][:5]
        return {k: out.get(k) for k in SUGGESTABLE if out.get(k)}
    titles = [e.get("title", "") for e in p.get("experience", []) if e.get("include", True) and e.get("title")]
    roles = list(dict.fromkeys(t for t in titles if "intern" not in t.lower())) or ["Software Engineer"]
    city = (p.get("location") or "").split(",")[0].strip()
    return {"target_roles": roles[:4],
            "work_preferences": "Remote worldwide" + (f", or onsite in {city}" if city else "")}


def fill_blanks(p, suggestions):
    """Only fill fields the user hasn't filled themselves."""
    p = dict(p)
    for k, v in suggestions.items():
        if not p.get(k):
            p[k] = v
    return p


def search_from_profile(p, cfg):
    """Turn a profile into this user's search settings (they can fine-tune them in Settings)."""
    roles = [r.lower() for r in p.get("target_roles", []) if r]
    skills = {s.lower() for row in p.get("skills", {}).values() for s in row if len(s) <= 24}
    skills |= {s[:-3] for s in skills if s.endswith(".js")}
    cfg["search_terms"] = roles[:6] or cfg["search_terms"]
    cfg["title_keywords"] = list(dict.fromkeys(roles + cfg["title_keywords"]))
    cfg["skills"] = sorted(skills) or cfg["skills"]
    loc_words = [w.strip().lower() for w in re.split(r"[,/]", p.get("location", "")) if w.strip()]
    cfg["open_locations"] = list(dict.fromkeys(cfg["open_locations"] + loc_words))
    years = re.search(r"(\d+(?:\.\d+)?)", p.get("years_experience_text", ""))
    if years and float(years.group(1)) >= 4:      # experienced: only staff+ titles count as too senior
        cfg["too_senior"] = ["staff", "principal", "director", "head of", "vp ", "10+ years"]
    if loc_words:
        cfg["linkedin"]["locations"] = list(dict.fromkeys(["Worldwide", loc_words[-1].title()]))
        cfg["jobspy"]["locations"] = ["Remote", p["location"]]
    gh = p.get("links", {}).get("GitHub", "")
    if gh and not cfg.get("github_user"):
        cfg["github_user"] = gh.rstrip("/").split("/")[-1]
    return cfg


def _context(profile, gh):
    exp = [e for e in profile["experience"] if e.get("include", True)]
    gh_small = [{k: v for k, v in r.items() if k not in ("pushed", "include")} for r in gh]
    return (f"<profile>\n{json.dumps({**profile, 'experience': exp}, indent=1)}\n</profile>\n\n"
            f"<github_projects>\n{json.dumps(gh_small, indent=1)}\n</github_projects>\n\n")


def tailor(jd, profile, gh, company_hint=""):
    prompt = (_context(profile, gh) +
              f"<job_description>\n{jd[:14000]}\n</job_description>\n"
              f"{'Company hint: ' + company_hint if company_hint else ''}\n\n"
              f"Return JSON matching this schema:\n{SCHEMA}")
    return validate(_ask(SYSTEM, prompt, 5000), profile)


def validate(out, profile):
    """Drop anything the model returned that is not grounded in the profile."""
    ids = {e["id"] for e in profile["experience"]}
    out["experience"] = [e for e in out.get("experience", []) if e.get("id") in ids]
    allowed = {s.lower() for row in profile["skills"].values() for s in row}
    for row in out.get("skills", []):
        dropped = [i for i in row["items"] if i.lower() not in allowed]
        row["items"] = [i for i in row["items"] if i.lower() in allowed]
        if dropped:
            out.setdefault("gaps", []).append(f"Removed ungrounded skills: {', '.join(dropped)}")
    out["skills"] = [r for r in out.get("skills", []) if r["items"]]
    for k in ("keywords_matched", "gaps", "projects"):
        out.setdefault(k, [])
    return out


def fallback(profile, role="Software Engineer"):
    """No-API version: your full base CV, unmodified."""
    return {
        "company": "Unknown", "role": role, "match_score": 0,
        "headline": profile.get("headline", "Full Stack Engineer | React, Node.js, Python, AI"),
        "summary": profile["base_summary"],
        "skills": [{"label": k, "items": v} for k, v in profile["skills"].items()],
        "experience": [{"id": e["id"], "bullets": e["bullets"][:4]} for e in profile["experience"] if e.get("include", True)],
        "projects": [{"id": p["id"], "name": p["name"], "tech": p["tech"], "url": p.get("url", ""),
                      "bullets": p["bullets"][:2]} for p in profile["projects"][:4]],
        "cover_letter": "(Set ANTHROPIC_API_KEY to generate a tailored cover letter.)",
        "email_subject": f"Application: {role} - {profile['name']}",
        "email_body": "(Set ANTHROPIC_API_KEY to generate a tailored email.)",
        "keywords_matched": [], "gaps": [],
    }


MATCH_SYSTEM = """You are a strict technical recruiter screening one job for one candidate. Score how likely the candidate gets an interview, 0-100.
Calibration: 90+ = meets essentially every hard requirement (stack, seniority/years, location/work authorisation) and most nice-to-haves; 75-89 = strong fit with one soft gap; 50-74 = plausible stretch; below 50 = missing a hard requirement.
Hard blockers cap the score at 40: the job is restricted to a country/region the candidate cannot work from, requires clearly more years than the candidate has, or its core language/stack is absent from the profile.
Eligibility: read the small print (location limits, timezone overlap, citizenship/clearance, "must be based in", visa sponsorship) and decide if THIS candidate, living where they live, can take the job:
"yes" = open to them, "no" = they can't (explain in a few words, e.g. "US residents only"), "unclear" = posting doesn't say.
If the candidate's stated preferences (liked/rejected examples) are given, nudge the score by at most 10 toward what they like.
Use ONLY the profile. Return ONLY JSON: {"match": 0-100, "verdict": "one sentence", "strengths": ["max 3"], "gaps": ["max 3"], "eligible": "yes|no|unclear", "eligibility": "max 8 words"}"""


def match_job(j, profile, prefs_text=""):
    """AI fit score + can-they-actually-take-it check for one scraped job. Compact context keeps it cheap."""
    small = {k: profile[k] for k in ("location", "work_preferences", "years_experience_text", "target_roles", "skills",
                                     "base_summary") if profile.get(k)}
    small["experience"] = [{k: e.get(k, "") for k in ("title", "company", "dates", "bullets")}
                           for e in profile["experience"] if e.get("include", True)]
    small["projects"] = [{"name": p["name"], "tech": p.get("tech", "")} for p in profile.get("projects", [])]
    prompt = (f"<candidate>\n{json.dumps(small)}\n</candidate>\n\n"
              + (f"<preferences>\n{prefs_text}\n</preferences>\n\n" if prefs_text else "")
              + f"<job>\nTitle: {j['title']}\nCompany: {j['company']}\nLocation: {j['location']}\n"
                f"Source: {j['source']}\n\n{j['desc'][:6000]}\n</job>")
    out = _ask(MATCH_SYSTEM, prompt, 700)
    out["match"] = max(0, min(100, int(out.get("match", 0))))
    if out.get("eligible") not in ("yes", "no", "unclear"):
        out["eligible"] = "unclear"
    if out["eligible"] == "no":
        out["match"] = min(out["match"], 40)
    return out


FORM_SYSTEM = """You fill in job application forms for one candidate. Use ONLY facts from their PROFILE, GITHUB PROJECTS and APPLICATION DEFAULTS.
Write answers in first person, plain text, specific and short (most 40-120 words). No em dashes, no "passionate", no invented facts.
If a needed fact is missing (salary, notice period, visa...), write a placeholder in [square brackets] for them to fill.
Include: (1) every question the job posting itself asks applicants, then (2) the usual form questions:
"Why do you want to work here?", "Why are you a good fit for this role?", "Tell us about yourself", "Describe a relevant project you're proud of",
"What is your expected salary?", "What is your notice period / when can you start?", "Are you authorised to work in <location>? / Do you need sponsorship?",
"How many years of experience do you have with <top 2-3 required skills>?" (one answer covering them), "Short cover note (max 300 characters)", and the links (LinkedIn, GitHub, portfolio).
Return ONLY JSON: {"answers": [{"q": "question", "a": "answer"}]}"""

PREP_SYSTEM = """You prepare one candidate for an interview. Use ONLY the job description and the candidate's profile; never invent company facts (say "check their website" instead).
Return ONLY JSON:
{"company_brief": "3-4 sentences on what the JD says about the company, team and product",
 "focus": ["5 skills/areas this interview will probably test, from the JD"],
 "questions": [{"q": "likely question", "type": "technical|behavioural|experience|system design", "answer": "how THIS candidate should answer, citing their real projects and numbers, 2-4 sentences"}],
 "ask_them": ["5 smart questions the candidate can ask"],
 "watch_out": ["2-4 gaps they may probe and how to handle each honestly"]}
Give 10 questions: about 4 technical, 3 experience/project deep-dives, 2 behavioural, 1 system design."""


def form_answers(profile, gh, jd, company="", role=""):
    defaults = profile.get("application_defaults") or {}
    prompt = (_context(profile, gh) + f"<application_defaults>\n{json.dumps(defaults)}\n</application_defaults>\n\n"
              f"<job_description>\nCompany: {company}\nRole: {role}\n\n{jd[:10000]}\n</job_description>")
    return _ask(FORM_SYSTEM, prompt, 3500).get("answers", [])


def interview_prep(profile, gh, jd, company="", role=""):
    prompt = _context(profile, gh) + f"<job_description>\nCompany: {company}\nRole: {role}\n\n{jd[:10000]}\n</job_description>"
    return _ask(PREP_SYSTEM, prompt, 4000)


def outreach(kind, profile, gh, company="", role="", recipient="", jd="", notes=""):
    """Recruiter / referral / follow-up message. Falls back to a template without an API key."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        return fallback_outreach(kind, profile, company, role, recipient)
    prompt = (_context(profile, gh) +
              f"<job_description>\n{(jd or '(not provided)')[:8000]}\n</job_description>\n\n"
              f"Message type: {OUTREACH[kind]}\nCompany: {company or 'unknown'}\nRole: {role or 'unknown'}\n"
              f"Recipient: {recipient or 'unknown'}\nExtra context from the candidate: {notes or 'none'}")
    out = _ask(OUTREACH_SYSTEM, prompt, 1200)
    if kind == "linkedin_note":
        out["body"] = out["body"][:300]
    return out


def fallback_outreach(kind, profile, company, role, recipient):
    first = profile["name"].split()[0]
    hi = f"Hi {recipient.split()[0]}," if recipient else "Hi there,"
    role, company = role or "the open engineering role", company or "your team"
    proofs = "".join(f"\n- {p}" for p in (profile["experience"][0]["bullets"][:2] if profile["experience"] else []))
    sign = f"\n\nThanks,\n{first}\n{profile['links'].get('Portfolio') or profile['links'].get('LinkedIn', '')}"
    t = {
        "cold_email": (f"{role} at {company} - {profile['name']}",
                       f"{hi}\n\nI'm applying for {role} at {company}. A couple of things I've shipped recently:{proofs}\n\n"
                       f"Would you be open to a 15 minute call, or could you point me to the right person?{sign}"),
        "linkedin_note": ("", f"{hi} full stack engineer here, applying for {role} at {company}. "
                              f"Would love to connect and hear about the team."[:300]),
        "linkedin_message": ("", f"{hi}\n\nI just applied for {role} at {company}.{proofs}\n\n"
                                 f"Are you the right person to talk to about it?{sign}"),
        "referral_ask": ("", f"{hi}\n\nI'm applying for {role} at {company} ([job link]). Would you be open to a quick chat "
                             f"about the team, or to referring me if you think I'd be a fit? No pressure at all.{sign}"),
        "follow_up": (f"Following up: {role} application",
                      f"{hi}\n\nFollowing up on my application for {role} last week. I'm still very interested and happy "
                      f"to share more detail on any of my work.{sign}"),
        "thank_you": (f"Thank you - {role} interview",
                      f"{hi}\n\nThanks for the conversation today. I enjoyed discussing [topic discussed] and it made the "
                      f"role even more appealing. Happy to send anything else that would help.{sign}"),
    }[kind]
    return {"subject": t[0], "body": t[1]}
