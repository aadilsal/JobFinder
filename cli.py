#!/usr/bin/env python3
"""
jobkit - find jobs and generate a tailored CV, cover letter and recruiter emails per job.

Server (the web app most people use):
  python cli.py serve [--port 8000]       # PWA + API + background job watcher

Admin:
  python cli.py users                     # list accounts
  python cli.py invite                    # print an invite link to send a friend
  python cli.py reset-auth <user>         # user lost their phone: print a re-enrol link

Per user (-u USER, or the only user / JOBKIT_USER):
  python cli.py cycle                     # scrape all sources, AI-score, notify (once)
  python cli.py watch                     # ...forever, every SCRAPE_EVERY_HOURS
  python cli.py scrape                    # scrape + rank only
  python cli.py jobs [-n 20]              # list top matches
  python cli.py apply --job 7             # tailor CV + letter + email for scraped job #7
  python cli.py apply --jd jd.txt | --url <link> | (paste, then Ctrl-D / Ctrl-Z Enter)
  python cli.py outreach cold_email --company X --role Y [--to "Jane Doe"]
  python cli.py sync-github
  python cli.py import-profile profile.json
"""
import argparse, os, shutil, sys

import config  # loads .env.local / .env


def pick_user(arg):
    import auth
    if arg:
        return arg
    if os.getenv("JOBKIT_USER"):
        return os.getenv("JOBKIT_USER")
    us = list(auth.users())
    if len(us) == 1:
        return us[0]
    sys.exit("Pass -u USER (accounts: " + (", ".join(us) or "none yet - sign up in the web app first") + ")")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-u", "--user")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve"); s.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)))
    s.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"))
    sub.add_parser("users"); sub.add_parser("invite")
    r = sub.add_parser("reset-auth"); r.add_argument("target")
    for c in ("cycle", "watch", "scrape", "sync-github"):
        sub.add_parser(c)
    j = sub.add_parser("jobs"); j.add_argument("-n", type=int, default=20)
    a = sub.add_parser("apply")
    a.add_argument("--job", type=int); a.add_argument("--jd"); a.add_argument("--url")
    a.add_argument("--company", default=""); a.add_argument("--theme")
    o = sub.add_parser("outreach")
    o.add_argument("kind", choices=["cold_email", "linkedin_note", "linkedin_message", "referral_ask", "follow_up", "thank_you"])
    o.add_argument("--company", default=""); o.add_argument("--role", default=""); o.add_argument("--to", default="")
    o.add_argument("--jd", help="file with the job description")
    i = sub.add_parser("import-profile"); i.add_argument("file")
    args = ap.parse_args()

    if args.cmd == "serve":
        import uvicorn
        uvicorn.run("server:app", host=args.host, port=args.port, proxy_headers=True, forwarded_allow_ips="*")
        return
    if args.cmd in ("users", "invite", "reset-auth"):
        import auth
        if args.cmd == "users":
            for u in auth.public_users():
                print(f"{u['uid']:<20} {'admin' if u['admin'] else '':<6} profile={u['has_profile']} created={u['created']}")
        base = os.getenv("PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")
        if args.cmd == "invite":
            print(f"{base}/#/join/{auth.create_invite('cli')}")
        elif args.cmd == "reset-auth":
            print(f"Re-enrol link for {args.target}: {base}/#/join/{auth.reset_user(args.target, 'cli')}")
        return

    uid = pick_user(args.user)
    if args.cmd == "import-profile":
        shutil.copy(args.file, config.profile_path(uid)); print(f"Imported into {config.profile_path(uid)}")
    elif args.cmd == "cycle":
        import watcher; watcher.cycle(uids=[uid])
    elif args.cmd == "watch":
        import watcher; watcher.watch()
    elif args.cmd == "scrape":
        import scraper; scraper.run(uid)
    elif args.cmd == "sync-github":
        import github_sync; print(f"Synced {len(github_sync.sync(uid))} repos")
    elif args.cmd == "jobs":
        import scraper, watcher
        for r in watcher.attach_ai(uid, scraper.load_jobs(uid))[:args.n]:
            ai = f"{r['ai_match']:>3}%" if "ai_match" in r else "  - "
            print(f"#{r['id']:<4}{'NEW ' if r['new'] else '    '}{r['score']:>3} {ai}  {r['title'][:46]:<46} "
                  f"{r['company'][:22]:<22} {r['location'][:20]}")
    elif args.cmd == "apply":
        import applier, scraper
        job, jd = None, ""
        if args.job:
            job = next(x for x in scraper.load_jobs(uid) if x["id"] == args.job)
        elif args.jd:
            jd = open(args.jd, encoding="utf-8").read()
        elif args.url:
            jd = applier.fetch_url(args.url)
        else:
            print("Paste the job description, then press Ctrl-D (Ctrl-Z Enter on Windows):"); jd = sys.stdin.read()
        name, c, _ = applier.apply(uid, jd, args.company, job, args.theme)
        print(f"\nMatch {c['match_score']}/100 | {c['role']} @ {c.get('company')}\n"
              f"Saved to {config.out_dir(uid) / name}")
        for g in c["gaps"]:
            print(f"  gap: {g}")
    elif args.cmd == "outreach":
        import generator
        profile, gh = generator.load_inputs(uid)
        jd = open(args.jd, encoding="utf-8").read() if args.jd else ""
        m = generator.outreach(args.kind, profile, gh, args.company, args.role, args.to, jd)
        print((f"Subject: {m['subject']}\n\n" if m.get("subject") else "") + m["body"])


if __name__ == "__main__":
    main()
