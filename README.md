# jobkit

**A self-hosted job-search copilot.** It scans 15 job sources every few hours, has Claude score every promising job against *your* CV, pings your phone when something scores 90%+, and turns any job you like into a tailored one-page CV, cover letter, application email and recruiter messages in about a minute.

- Installable **PWA** (Android, iPhone, desktop) with **push notifications**
- **Multi-user** with **authenticator-app login** (no passwords), invite-only sign-up
- **CV onboarding:** upload your CV, it fills in your profile and asks only for what's missing
- **Honest by design:** the AI may select, reorder and reword *your* facts, never invent them. Missing skills are reported as gaps.
- Runs free, 24/7, on an Oracle Cloud "Always Free" VM (or any Docker host)

---

## How it works

```
 every 6 hours (or "Scan now")
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ 1. Scrape 15 sources once for everyone (≈3,000-4,000 jobs, ~20 s)        │
 │ 2. Per user: keyword-rank against their profile (skills, titles, where   │
 │    they can work, seniority)                                             │
 │ 3. Claude scores the best new ones 0-100: "how likely is an interview?"  │
 │ 4. 90%+  →  push notification / ntfy / Telegram                          │
 │ 5. Follow-ups due  →  daily reminder                                     │
 └──────────────────────────────────────────────────────────────────────────┘
 You tap a job → Generate → CV.pdf + Cover_Letter.pdf + email + recruiter DMs
                → mark Applied → reminder to follow up in 7 days
```

### Job sources

| Type | Sources | Setup |
|---|---|---|
| Remote boards | Remotive, RemoteOK, Arbeitnow, Himalayas, Jobicy, We Work Remotely, Working Nomads | none |
| Community | Hacker News "Who is hiring?" (latest thread) | none |
| Company career pages | Greenhouse, Lever, Ashby boards for any companies you list | add company slugs in Settings |
| Aggregators | LinkedIn public listings (logged-out view) | none |
| | Adzuna | free key: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` |
| | JSearch (Google for Jobs: LinkedIn, Indeed, Glassdoor, ZipRecruiter...) | `RAPIDAPI_KEY` |
| | JobSpy (Indeed, Glassdoor, Google, ZipRecruiter) | `pip install python-jobspy` |

Each user can switch sources on or off and edit keywords, locations and companies in **Settings**.

### What's in the app

| Page | What you do there |
|---|---|
| **Overview** | Strong matches, new jobs, pipeline, follow-ups due, source health, "Scan now" with a live log |
| **Jobs** | Search and filter (90%+, new, shortlisted, AI-scored, hidden), shortlist or hide, open a job to see the AI verdict, strengths and gaps |
| **Tailor & apply** | Paste any job description or URL to generate an application package |
| **Application package** | Live PDF preview, switch CV design, edit summary, bullets, letter and email, then rebuild; open in your email app; generate recruiter messages |
| **Applications** | Status pipeline (drafted, applied, interviewing, offer...), contacts, dates and notes; "applied" schedules a follow-up |
| **Outreach** | Cold email, LinkedIn connection note (300 chars), LinkedIn message, referral ask, follow-up, thank-you, plus a playbook |
| **Profile & CV** | Edit your profile, re-import a CV, preview the 4 CV designs with your data, sync GitHub repos to use as projects |
| **Settings** | Notifications (push, ntfy, Telegram, alert threshold), search keywords, sources, company boards |
| **Admin** | Invite people, reset a lost authenticator, remove users, check server keys |

**CV designs:** Classic (black and white, safest for ATS), Modern (blue accents), Executive (serif), Compact (fits more). All are single column with real text, so applicant tracking systems parse them cleanly.

---

## Run it locally (5 minutes)

```bash
git clone https://github.com/<you>/jobkit && cd jobkit
python -m venv .venv
.venv/Scripts/activate            # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env.local        # add ANTHROPIC_API_KEY
python cli.py serve               # http://127.0.0.1:8000
```

Open the app, create the first account (it becomes the **admin**), upload your CV and you're done. Push notifications need HTTPS, so locally use ntfy or deploy (below).

> Already have a `profile.json` (the old single-user format)? Put it in the project root before you sign up and the admin account inherits it. Or later: `python cli.py import-profile profile.json`.

---

## Deploy free, always on

Railway, Render and Hugging Face free tiers sleep, so the scheduler stops and notifications stop with it. Use a real free VM instead:

**Oracle Cloud Always Free** (recommended: up to 4 ARM CPUs / 24 GB RAM, free forever) or **Google Cloud e2-micro** (1 GB, free tier).

1. Create the VM: **Ubuntu 22.04/24.04**, shape *VM.Standard.A1.Flex* (Oracle) with 1 OCPU / 6 GB is plenty.
2. Open ports **80** and **443**: Oracle → VCN → Security List → add ingress rules for TCP 80 and 443 from `0.0.0.0/0`. (The setup script also opens the VM's own firewall.)
3. SSH in and run:
   ```bash
   git clone https://github.com/<you>/jobkit && cd jobkit
   bash deploy/setup-vm.sh                # creates .env.local and stops so you can add keys
   nano .env.local                        # ANTHROPIC_API_KEY=..., anything else you want
   bash deploy/setup-vm.sh                # builds and starts; prints your https:// URL
   ```
   With no domain it uses `<your-ip>.sslip.io`, which gets a real HTTPS certificate automatically through Caddy. If you have a domain (or a free DuckDNS one), point it at the VM and run `bash deploy/setup-vm.sh jobs.yourdomain.com`.
4. Open the URL **right away** and create your account. The first account on a fresh server becomes the admin; after that nobody can join without an invite link from you.

Day-to-day operations on the VM:

```bash
sudo docker compose logs -f jobkit                     # watch scans
git pull && sudo docker compose up -d --build          # update
sudo docker compose exec jobkit python cli.py invite   # invite link from the terminal
sudo docker compose exec jobkit python cli.py users
```

Your data lives in the `jobkit-data` Docker volume. Back it up with `sudo docker run --rm -v jobkit_jobkit-data:/d -v $PWD:/b alpine tar czf /b/jobkit-backup.tgz -C /d .`

> Oracle can reclaim Always Free VMs that sit nearly idle for 7 days. jobkit's scans keep it lightly busy; upgrading the account to Pay-As-You-Go (still $0 for Always Free resources) removes the risk entirely.

---

## Who can get in

It's your app. Someone who finds the site just sees a login page; they can't register.

- **You (owner/admin):** the first account created on a fresh server. Create it as soon as you deploy.
- **Friends:** Admin → **Create invite link** → send it. One tap opens a ready-made registration page (nothing to type except a username). Each link works **once**, expires after **7 days**, and can be revoked. They then onboard with their own CV, GitHub and preferences, and get their own jobs, CVs and alerts, fully separate from yours.
- **Cost:** invited users share your Anthropic key, so each gets `AI_DAILY_LIMIT` AI actions a day (default 30). You're unlimited.
- **Removing someone:** Admin → *Remove*; their sessions stop working immediately.
- Wrong codes are rate-limited (6 per username / 20 per IP per 10 minutes), and every code is single-use.

## Logging in: how it works for someone you invite

jobkit has **no passwords**. You log in with a 6-digit code from an authenticator app on your phone (the same thing banks and GitHub use for 2FA, called TOTP).

**What your friend needs:** a phone with an authenticator app. Any of these: Google Authenticator, Microsoft Authenticator, Authy, 1Password, Bitwarden.

**1. You invite them.** Admin → *Create invite link* → *Copy with message* (or *Share...* on your phone) and send it on WhatsApp or by email:
> Here's your invite to jobkit: https://your-url/#/join/Xy7... You'll need an authenticator app on your phone.

**2. They sign up** (about 2 minutes):
1. Tap the link and pick a username.
2. A QR code appears. In the authenticator app tap **+** → **Scan QR code**. (On the same phone? Tap **Open in authenticator**, or copy the setup key and paste it into the app.)
3. The app now shows a **jobkit (username)** entry with a 6-digit code that changes every 30 seconds. They type it in.
4. They get **8 recovery codes**. Each one logs in once if the phone is lost. They save them (download or copy into a password manager).
5. Onboarding: upload their CV → check the details → answer anything missing (for example "Where can you work?") → done. Their first matches appear within minutes.

**3. Logging in later:** username + whatever 6-digit code the app shows right now. Sessions last 30 days per device. Each code works only once, and repeated wrong codes lock the username for 10 minutes.

**Lost phone?** Log in with a recovery code, or ask the admin: Admin → *Reset authenticator* gives you a personal re-enrol link to send them (their sessions are logged out, and their data is kept). They tap it and scan a new QR code.

**Why this way:** there's no password to leak or reuse, nothing to reset by email, and the server stores only the TOTP secret plus hashed recovery codes. Keep the server's `data/` volume private: anyone with those files could mint codes.

---

## Notifications

| Channel | Works on | Setup |
|---|---|---|
| **Web Push** (built in) | Android Chrome, desktop browsers, **iPhone (iOS 16.4+) only after *Share → Add to Home Screen*** | Settings → *Enable push on this device* (needs HTTPS) |
| **ntfy** (backup, very reliable) | every phone | install the ntfy app, Settings → *Generate* a topic, subscribe to the same topic in the app |
| **Telegram** | every phone | admin sets `TELEGRAM_BOT_TOKEN`; each user adds their chat id in Settings |

You're notified when a job's AI match is at or above your threshold (default **90**, adjustable), and once a day when follow-ups are due.

---

## Configuration (`.env.local`)

| Variable | Needed | What for |
|---|---|---|
| `ANTHROPIC_API_KEY` | **yes** | CV parsing, match scores, tailoring, outreach |
| `AI_DAILY_LIMIT` | optional | AI actions per invited user per day (default 30; you're unlimited) |
| `GITHUB_TOKEN` | recommended | avoids GitHub rate limits when syncing repos (no scopes needed) |
| `VAPID_EMAIL` | recommended | contact address sent to push services |
| `JOBKIT_MODEL` | optional | defaults to `claude-sonnet-5-5` |
| `SCRAPE_EVERY_HOURS` | optional | default 6 |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` / `RAPIDAPI_KEY` | optional | extra sources |
| `TELEGRAM_BOT_TOKEN`, `NTFY_SERVER` | optional | notification channels |

**AI cost:** each scan AI-scores at most 25 new jobs per user (only ones that already pass the keyword filter), and each tailored application is one call. Typical personal use is a few dollars a month. Lower `ai_score_top_n` in Settings to spend less.

---

## CLI

```bash
python cli.py serve                  # web app + background watcher
python cli.py cycle                  # one scan + AI scoring + notifications, then exit (cron-friendly)
python cli.py jobs -n 20             # top matches in the terminal
python cli.py apply --job 7          # tailor for job #7  (or --jd file.txt / --url ... / paste)
python cli.py outreach cold_email --company Acme --role "Backend Engineer" --to "Jane Doe"
python cli.py sync-github
python cli.py users | invite | reset-auth <user>
```

With more than one user, add `-u <username>` (or set `JOBKIT_USER`).

---

## Project layout

```
server.py        FastAPI: JSON API + serves the PWA + starts the watcher
watcher.py       scheduler: scrape → rank per user → AI score → notify
scraper.py       15 sources, dedupe, keyword scoring
generator.py     Claude prompts: CV parsing, match score, tailoring, outreach (+ grounding checks)
render.py        CV + cover letter PDFs (4 designs)
applier.py       builds an application package, safe URL fetching
auth.py          TOTP sign-up and login, invites, sessions, recovery codes
notify.py        Web Push (VAPID), ntfy, Telegram
tracker.py       application pipeline per user
github_sync.py   pulls each user's repos to use as projects
config.py        paths, .env.local loading, per-user settings
web/             the PWA (vanilla JS, no build step)
deploy/          VM setup script;  Dockerfile, docker-compose.yml, Caddyfile at the root
data/            all user data (gitignored; a Docker volume in production)
```

## Honest limits

- No tool can guarantee a job. jobkit makes sure you see the right openings early and never send a sloppy application. The interviews are still up to you.
- Always read the letter and email before sending. Check the **gaps** list on every package.
- LinkedIn's logged-out listings are scraped politely (capped, rate-limited). Their terms discourage scraping; turn the source off in Settings if that matters to you. Indeed and Glassdoor block direct scraping, so use JSearch or JobSpy for those.
- Keyword pre-filtering decides which jobs reach the AI. If good jobs are missing, widen *Search terms*, *Title must contain* and *Locations you can work from* in Settings.
