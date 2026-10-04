"use strict";
/* jobkit PWA - vanilla JS, no build step. Hash routes: #/, #/jobs, #/jobs/<key>, #/apply, #/apply/<folder>,
   #/applications, #/outreach, #/profile, #/settings, #/admin, #/more, #/login, #/signup, #/onboarding */

// ---------- utils ----------
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
const raw = (s) => new Raw(s);
const fmt = (v) => (v instanceof Raw ? v.s : Array.isArray(v) ? v.map(fmt).join("") : v === false || v == null ? "" : esc(v));
const html = (strs, ...vals) => raw(strs.reduce((a, s, i) => a + s + (i < vals.length ? fmt(vals[i]) : ""), ""));
const set = (el, h) => { el.innerHTML = fmt(h); return el; };
const go = (hash) => { if (location.hash === hash) route(); else location.hash = hash; };
const store = { get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
                set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } } };
const splitList = (s) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);
const splitLines = (s) => s.split("\n").map((x) => x.trim().replace(/^[-•]\s*/, "")).filter(Boolean);
const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent);
const standalone = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;

function ago(iso) {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 0) { const m = Math.round(-s / 60); return m < 60 ? `in ${m} min` : `in ${Math.round(m / 60)} h`; }
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

const ICONS = {
  home: '<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
  search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  file: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  list: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
  mail: '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>',
  user: '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  ext: '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>',
  bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
  hide: '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>',
  refresh: '<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>',
};
const icon = (n) => raw(`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[n]}</svg>`);

const S = { me: null, poll: null, install: null, themes: null };

async function api(method, path, body) {
  const opt = { method, headers: { "X-Requested-With": "jobkit" }, credentials: "same-origin" };
  if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
  let res;
  try { res = await fetch(path, opt); } catch { throw new Error("Can't reach the server. Check your connection."); }
  if (res.status === 401 && !path.startsWith("/api/auth")) { S.me = null; go("#/login"); throw new Error("Please log in"); }
  const data = (res.headers.get("content-type") || "").includes("json") ? await res.json() : await res.text();
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : `${res.status} ${res.statusText}`);
  }
  return data;
}

function toast(msg, ms = 3600) {
  const t = Object.assign(document.createElement("div"), { className: "toast", textContent: msg, role: "status" });
  document.body.append(t);
  setTimeout(() => t.remove(), ms);
}

async function busy(btn, fn) {
  const label = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> ${esc(btn.dataset.busy || "Working...")}`;
  try { return await fn(); } catch (e) { toast(e.message, 6000); } finally { btn.disabled = false; btn.innerHTML = label; }
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast("Copied"); } catch { toast("Copy failed - select and copy manually"); }
}

const readFileB64 = (file) => new Promise((ok, bad) => {
  const r = new FileReader();
  r.onload = () => ok(String(r.result).split(",")[1] || "");
  r.onerror = () => bad(new Error("Couldn't read that file"));
  r.readAsDataURL(file);
});

// ---------- shared bits ----------
const STATUS_COLORS = { drafted: "#94a3b8", applied: "#3b82f6", "follow-up sent": "#6366f1", interviewing: "#f59e0b",
                        offer: "#16a34a", rejected: "#ef4444", ghosted: "#64748b" };
const KINDS = { cold_email: "Cold email to recruiter / hiring manager", linkedin_note: "LinkedIn connection note (300 chars)",
                linkedin_message: "LinkedIn message to recruiter", referral_ask: "Ask an employee for a referral",
                follow_up: "Follow-up after applying", thank_you: "Thank-you after an interview" };

function scoreBox(r) {
  if (r.ai_match != null) {
    const cls = r.ai_match >= (S.me?.threshold || 90) ? "s-hi" : r.ai_match >= 70 ? "s-mid" : "";
    return html`<div class="score ${cls}" title="AI match: how likely you get an interview">${r.ai_match}<small>match</small></div>`;
  }
  return html`<div class="score" title="Keyword score (not AI-scored yet)">${r.score}<small>keywords</small></div>`;
}

function jobItem(r, actions = true) {
  const [skills, flags] = String(r.why || "").split(" | ");
  return html`<div class="item" data-key="${r.key}">
    ${scoreBox(r)}
    <div class="body">
      <a class="title" href="#/jobs/${r.key}">${r.title}</a>
      <div class="meta">${r.company || "Unknown company"} &middot; ${r.location || "Location n/a"} &middot; ${r.source}${r.date ? ` · ${r.date}` : ""}</div>
      <div class="chips" style="margin-top:6px">
        ${r.new ? html`<span class="badge acc">New</span>` : ""}
        ${r.state === "shortlisted" ? html`<span class="badge good">Shortlisted</span>` : ""}
        ${r.state === "applied" ? html`<span class="badge good">Applied</span>` : ""}
        ${(flags || "").split(" ").filter(Boolean).map((f) => html`<span class="badge warn">${f}</span>`)}
        ${(skills || "").split(", ").filter(Boolean).slice(0, 5).map((s) => html`<span class="badge">${s}</span>`)}
      </div>
    </div>
    ${actions ? html`<div class="acts">
      <button class="btn sm" data-star="${r.key}" title="Shortlist" aria-label="Shortlist">${icon("star")}${r.state === "shortlisted" ? " Saved" : ""}</button>
      <button class="btn sm" data-hide="${r.key}" title="${r.state === "hidden" ? "Unhide" : "Hide"}" aria-label="Hide">${icon("hide")}</button>
    </div>` : ""}
  </div>`;
}

function bindJobActions(el, rows, rerender) {
  $$("[data-star]", el).forEach((b) => (b.onclick = async () => {
    const r = rows.find((x) => x.key === b.dataset.star);
    r.state = r.state === "shortlisted" ? "" : "shortlisted";
    await api("POST", `/api/jobs/${r.key}/state`, { state: r.state }).catch((e) => toast(e.message));
    rerender();
  }));
  $$("[data-hide]", el).forEach((b) => (b.onclick = async () => {
    const r = rows.find((x) => x.key === b.dataset.hide);
    r.state = r.state === "hidden" ? "" : "hidden";
    await api("POST", `/api/jobs/${r.key}/state`, { state: r.state }).catch((e) => toast(e.message));
    toast(r.state === "hidden" ? "Hidden" : "Unhidden");
    rerender();
  }));
}

function themeSelect(id, current) {
  return html`<select id="${id}" aria-label="CV design" style="width:auto">${(S.themes || []).map((t) =>
    html`<option value="${t.id}" ${t.id === current ? "selected" : ""}>${t.label.split(" - ")[0]} design</option>`)}</select>`;
}

async function loadThemes() { if (!S.themes) S.themes = await api("GET", "/api/themes"); return S.themes; }

function b64u(s) {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const b = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(b, (c) => c.charCodeAt(0));
}

async function enablePush() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    throw new Error(isIOS() && !standalone()
      ? "On iPhone: tap Share > Add to Home Screen, open jobkit from the Home Screen, then enable notifications."
      : "This browser can't receive push notifications. Use the ntfy option instead.");
  }
  if (!isSecureContext) throw new Error("Push needs HTTPS. Open jobkit through its https:// address.");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Notifications are blocked. Allow them for this site in your browser settings.");
  const reg = await navigator.serviceWorker.ready;
  const { key } = await api("GET", "/api/push/key");
  let sub = await reg.pushManager.getSubscription();
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64u(key) });
  const r = await api("POST", "/api/push/subscribe", sub.toJSON());
  S.me = null;
  return r;
}

// ---------- layout ----------
function navItems() {
  const items = [["#/", "Overview", "home"], ["#/jobs", "Jobs", "search"], ["#/apply", "Tailor & apply", "file"],
    ["#/applications", "Applications", "list"], ["#/outreach", "Outreach", "mail"], ["#/profile", "Profile & CV", "user"],
    ["#/settings", "Settings", "settings"]];
  if (S.me?.admin) items.push(["#/admin", "Admin", "shield"]);
  return items;
}
const isActive = (href, path) => (href === "#/" ? path === "#/" || path === "#" || path === "" : path.startsWith(href));

function shell(path) {
  const root = $("#root");
  if (!$("#main")) {
    set(root, html`<div class="app">
      <aside class="side">
        <div class="brand"><img src="/icons/icon-192.png" alt="">jobkit</div>
        <nav class="nav" id="nav"></nav>
        <div class="foot">
          <button class="btn sm hidden" id="installBtn">Install app</button>
          <span class="muted small" id="who"></span>
          <a href="#" class="small" id="logout">Log out</a>
        </div>
      </aside>
      <div>
        <header class="topbar"><div class="brand"><img src="/icons/icon-192.png" alt="">jobkit</div>
          <a class="btn sm" href="#/settings" aria-label="Notification settings">${icon("bell")}</a></header>
        <main id="main"></main>
      </div>
      <nav class="tabbar" id="tabbar"></nav>
    </div>`);
    $("#logout").onclick = async (e) => { e.preventDefault(); await api("POST", "/api/auth/logout"); S.me = null; go("#/login"); };
    $("#installBtn").onclick = async () => { if (S.install) { S.install.prompt(); S.install = null; $("#installBtn").classList.add("hidden"); } };
  }
  $("#who").textContent = `Signed in as ${S.me.uid}`;
  if (S.install) $("#installBtn").classList.remove("hidden");
  set($("#nav"), navItems().map(([h, l, i]) => html`<a href="${h}" class="${isActive(h, path) ? "active" : ""}">${icon(i)}${l}</a>`));
  const tabs = [["#/", "Home", "home"], ["#/jobs", "Jobs", "search"], ["#/apply", "Apply", "file"], ["#/applications", "Tracker", "list"], ["#/more", "More", "more"]];
  const moreActive = ["#/outreach", "#/profile", "#/settings", "#/admin", "#/more"].some((p) => path.startsWith(p));
  set($("#tabbar"), tabs.map(([h, l, i]) => html`<a href="${h}" class="${(h === "#/more" ? moreActive : isActive(h, path)) ? "active" : ""}">${icon(i)}${l}</a>`));
}

// ---------- router ----------
const routes = [
  [/^#\/login$/, pageLogin, "public"],
  [/^#\/signup$/, pageSignup, "public"],
  [/^#\/join\/([\w-]+)$/, pageSignup, "public"],
  [/^#\/onboarding$/, pageOnboarding, "bare"],
  [/^#\/jobs$/, pageJobs],
  [/^#\/jobs\/([\w-]+)$/, pageJob],
  [/^#\/apply$/, pageApply],
  [/^#\/apply\/(.+)$/, pagePackage],
  [/^#\/applications$/, pageApplications],
  [/^#\/outreach$/, pageOutreach],
  [/^#\/profile$/, pageProfile],
  [/^#\/settings$/, pageSettings],
  [/^#\/admin$/, pageAdmin],
  [/^#\/more$/, pageMore],
  [/^(#\/?)?$/, pageOverview],
];

async function route() {
  clearInterval(S.poll);
  const [path, qs] = (location.hash || "#/").split("?");
  const q = new URLSearchParams(qs || "");
  const hit = routes.find((r) => r[0].test(path)) || routes[routes.length - 1];
  const mode = hit[2];
  if (mode !== "public") {
    if (!S.me) { try { S.me = await api("GET", "/api/me"); } catch { return; } }
    if (!S.me.onboarded && mode !== "bare") return go("#/onboarding");
  }
  const m = path.match(hit[0]);
  const el = document.createElement("div");
  if (mode) { set($("#root"), ""); $("#root").append(el); }
  else {
    shell(path);
    set($("#main"), "");
    $("#main").append(el);
    set(el, html`<div class="empty"><span class="spinner"></span></div>`);
  }
  try { await hit[1](el, m, q); } catch (e) { if (e.message !== "Please log in") set(el, html`<div class="notice bad">${e.message}</div>`); }
  if (!mode) window.scrollTo(0, 0);
}

// ---------- auth pages ----------
async function pageLogin(el) {
  const st = await api("GET", "/api/auth/status");
  if (st.first_user) return go("#/signup");
  set(el, html`<div class="auth">
    <div class="brand"><img src="/icons/icon-192.png" alt="">jobkit</div>
    <div class="card">
      <h1>Log in</h1>
      <p class="muted small">Open your authenticator app and enter the 6-digit code it shows for <b>jobkit</b>.</p>
      <form id="f">
        <div class="field"><label for="uid">Username</label>
          <input id="uid" type="text" autocomplete="username" autocapitalize="none" spellcheck="false" required value="${store.get("uid", "")}"></div>
        <div class="field"><label for="code">Code</label>
          <input id="code" class="code-input" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="20" required placeholder="123456"></div>
        <button class="btn primary" style="width:100%" data-busy="Checking...">Log in</button>
      </form>
      <p class="small muted" style="margin-top:14px">Lost your phone? Enter one of your recovery codes instead of the 6-digit code, or ask the owner for a re-enrol link.</p>
    </div>
    <p class="small muted" style="text-align:center;margin-top:14px">New here? jobkit is invite-only. Open the invite link you were sent.</p>
  </div>`);
  ($("#uid", el).value ? $("#code", el) : $("#uid", el)).focus();
  $("#f", el).onsubmit = (e) => {
    e.preventDefault();
    busy($("button", el), async () => {
      const uid = $("#uid", el).value.trim().toLowerCase();
      await api("POST", "/api/auth/login", { uid, code: $("#code", el).value });
      store.set("uid", uid);
      S.me = null;
      go("#/");
    });
  };
}

async function pageSignup(el, m) {
  const st = await api("GET", "/api/auth/status");
  const draw = (step, body) => set(el, html`<div class="auth">
    <div class="brand"><img src="/icons/icon-192.png" alt="">jobkit</div>
    <div class="card"><div class="steps">${[1, 2, 3].map((i) => html`<span class="${i <= step ? "on" : ""}"></span>`)}</div>${body}</div>
    ${step === 1 ? html`<p class="small" style="text-align:center;margin-top:14px">Have an account? <a href="#/login">Log in</a></p>` : ""}
  </div>`);

  // #/join/<code> carries the invite in the link itself - nothing to type
  const invite = m && m[1] ? decodeURIComponent(m[1]) : "";
  const inv = invite ? await api("GET", `/api/auth/invite/${encodeURIComponent(invite)}`) : null;
  if (!st.first_user && !(inv && inv.valid)) return draw(1, html`<h1>${invite ? "This link doesn't work" : "Invite only"}</h1>
    <p class="muted">${invite ? "This invite link was already used or has expired (links last 7 days). Ask for a new one."
      : "jobkit is invite-only. Ask the owner to send you an invite link."}</p>`);
  const reenrol = inv && inv.for_user;

  draw(1, html`<h1>${reenrol ? "Set up your new phone" : st.first_user ? "Create the owner account" : "You're invited"}</h1>
    <p class="muted small">jobkit uses an authenticator app instead of a password. You'll need one on your phone:
      Google Authenticator, Microsoft Authenticator, Authy or 1Password all work.</p>
    ${st.first_user ? html`<div class="notice">This is a fresh server, so this account will be the admin. Only you can invite others afterwards.</div>` : ""}
    <form id="f">
      <div class="field"><label for="uid">${reenrol ? "Username" : "Pick a username"}</label>
        <input id="uid" type="text" autocomplete="username" autocapitalize="none" spellcheck="false" required placeholder="e.g. sara"
          ${reenrol ? raw(`value="${esc(reenrol)}" readonly`) : ""}>
        ${reenrol ? "" : html`<div class="small muted">3-32 characters: lowercase letters, digits, - or _</div>`}</div>
      <button class="btn primary" style="width:100%" data-busy="Setting up...">Continue</button>
    </form>`);
  $("#f", el).onsubmit = (e) => {
    e.preventDefault();
    busy($("button", el), async () => {
      const uid = $("#uid", el).value.trim().toLowerCase();
      const r = await api("POST", "/api/auth/signup/start", { uid, invite });
      step2(uid, r);
    });
  };

  function step2(uid, r) {
    draw(2, html`<h1>Connect your authenticator</h1>
      <ol class="small" style="padding-left:18px">
        <li>Open your authenticator app and tap <b>+</b> / <b>Add account</b>.</li>
        <li>Scan this QR code. On this phone? Tap <b>Open in authenticator</b> or type the setup key.</li>
        <li>Type the 6-digit code the app shows for <b>jobkit (${uid})</b>.</li>
      </ol>
      <img class="qr" src="${r.qr}" alt="QR code for your authenticator app">
      <div class="row" style="justify-content:center"><a class="btn sm" href="${r.uri}">Open in authenticator</a>
        <button class="btn sm" id="ck" type="button">Copy setup key</button></div>
      <p class="mono small" style="text-align:center;margin-top:8px">${r.secret.match(/.{1,4}/g).join(" ")}</p>
      <form id="f2">
        <div class="field"><label for="code">6-digit code</label>
          <input id="code" class="code-input" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="7" required placeholder="123456"></div>
        <button class="btn primary" style="width:100%" data-busy="Verifying...">Verify and create account</button>
      </form>`);
    $("#ck", el).onclick = () => copy(r.secret);
    $("#f2", el).onsubmit = (e) => {
      e.preventDefault();
      busy($("#f2 button", el), async () => {
        const res = await api("POST", "/api/auth/signup/finish", { uid, code: $("#code", el).value });
        store.set("uid", uid);
        step3(uid, res.recovery);
      });
    };
  }

  function step3(uid, codes) {
    const text = `jobkit recovery codes for ${uid}\nEach code works once if you lose your authenticator.\n\n${codes.join("\n")}\n`;
    draw(3, html`<h1>Save your recovery codes</h1>
      <p class="muted small">If you lose your phone, each of these codes logs you in once. Store them in a password manager or somewhere safe. You won't see them again.</p>
      <div class="codes">${codes.map((c) => html`<span>${c}</span>`)}</div>
      <div class="row"><button class="btn" id="cp" type="button">Copy</button>
        <a class="btn" download="jobkit-recovery-codes.txt" href="data:text/plain;charset=utf-8,${encodeURIComponent(text)}">Download .txt</a></div>
      <label class="switch" style="margin:16px 0"><input type="checkbox" id="ok"> I saved my recovery codes</label>
      <button class="btn primary" style="width:100%" id="go" disabled>Continue to set up your profile</button>`);
    $("#cp", el).onclick = () => copy(text);
    $("#ok", el).onchange = (e) => ($("#go", el).disabled = !e.target.checked);
    $("#go", el).onclick = () => { S.me = null; go("#/onboarding"); };
  }
}

// ---------- profile form (onboarding + profile page) ----------
const CORE = ["name", "email", "phone", "location", "links.LinkedIn", "links.GitHub", "links.Portfolio",
              "years_experience_text", "target_roles", "work_preferences", "base_summary"];

function profileForm(p, questions = []) {
  const miss = new Set(questions.filter((q) => q.required).map((q) => q.key));
  const f = (key, label, value, type = "text", hint = "") => html`<div class="field ${miss.has(key) ? "req" : ""}">
    <label for="pf-${key}">${label}${hint ? html` <span class="muted">${hint}</span>` : ""}</label>
    ${type === "textarea" ? html`<textarea id="pf-${key}" data-pf="${key}">${value}</textarea>`
      : html`<input id="pf-${key}" data-pf="${key}" type="${type}" value="${value}" ${miss.has(key) ? raw('style="border-color:var(--bad)"') : ""}>`}
  </div>`;
  const L = p.links || {};
  return html`<div class="spread" style="margin-bottom:12px"><span class="small muted">Job titles, headline, experience and where you can work can be filled for you.</span>
      <button type="button" class="btn sm" id="suggest" data-busy="Thinking...">✨ Suggest with AI</button></div>
    <div class="grid g2">
      ${f("name", "Full name", p.name)}${f("headline", "Headline", p.headline, "text", "e.g. Full Stack Engineer | React, Node.js")}
      ${f("email", "Email", p.email, "email")}${f("phone", "Phone", p.phone, "text", "with country code")}
      ${f("location", "Location", p.location, "text", "City, Country")}${f("years_experience_text", "Experience", p.years_experience_text, "text", "e.g. 2+ years of professional experience")}
      ${f("links.LinkedIn", "LinkedIn", L.LinkedIn || "")}${f("links.GitHub", "GitHub", L.GitHub || "", "text", "used to pull your projects")}
      ${f("links.Portfolio", "Portfolio / website", L.Portfolio || "")}${f("target_roles", "Target job titles", (p.target_roles || []).join(", "), "text", "comma separated")}
    </div>
    ${f("work_preferences", "Where can you work?", p.work_preferences, "text", "remote worldwide, onsite city, relocation...")}
    ${f("base_summary", "Professional summary", p.base_summary, "textarea")}`;
}

const SUGGESTABLE = ["target_roles", "headline", "years_experience_text", "work_preferences"];

// "Suggest with AI": fills the 4 job-search fields in place, keeping every other edit on the page
function bindSuggest(el, getBase) {
  const btn = $("#suggest", el);
  if (!btn) return;
  btn.onclick = () => busy(btn, async () => {
    const current = readAdvanced(el, readProfileForm(el, getBase()));
    const r = await api("POST", "/api/profile/suggest", { profile: current, overwrite: true });
    for (const k of SUGGESTABLE) {
      const input = $(`[data-pf="${k}"]`, el), v = r.suggested[k];
      if (input && v) {
        input.value = Array.isArray(v) ? v.join(", ") : v;
        input.style.borderColor = "var(--accent)";
      }
    }
    toast("Filled in. Edit anything that's off, then save.");
  });
}

function readProfileForm(el, base) {
  const p = JSON.parse(JSON.stringify(base));
  p.links = { ...(p.links || {}) };
  $$("[data-pf]", el).forEach((i) => {
    const k = i.dataset.pf, v = i.value.trim();
    if (k.startsWith("links.")) { if (v) p.links[k.slice(6)] = v; else delete p.links[k.slice(6)]; }
    else if (k === "target_roles") p.target_roles = splitList(v);
    else p[k] = v;
  });
  return p;
}

// ---- structured editor for experience / projects / skills / education ----
const fieldIn = (f, label, value, ph = "") => html`<div class="field"><label>${label}</label><input type="text" data-f="${f}" value="${value || ""}" placeholder="${ph}"></div>`;
const bulletsIn = (value, ph) => html`<div class="field"><label>Achievements <span class="muted">(one per line, numbers help)</span></label>
  <textarea data-f="bullets" placeholder="${ph}">${(value || []).join("\n")}</textarea></div>`;
const delBtn = (what) => html`<button type="button" class="btn sm danger" data-adv-del>Remove ${what}</button>`;

const ADV_ITEMS = {
  skill: (s) => html`<div class="adv-item" data-kind="skill"><div class="adv-row">
      <div class="field" style="flex:0 0 200px"><label>Group</label><input type="text" data-f="label" value="${s.label || ""}" placeholder="e.g. Backend"></div>
      <div class="field" style="flex:1"><label>Skills <span class="muted">(comma separated)</span></label><input type="text" data-f="items" value="${(s.items || []).join(", ")}" placeholder="Node.js, Express, FastAPI"></div>
      <button type="button" class="btn sm danger" data-adv-del aria-label="Remove group" style="margin-top:22px">&times;</button></div></div>`,
  exp: (e) => html`<div class="adv-item" data-kind="exp" data-id="${e.id || ""}">
      <div class="grid g2">${fieldIn("title", "Job title", e.title, "Full Stack Engineer")}${fieldIn("company", "Company", e.company, "Acme")}
        ${fieldIn("location", "Location", e.location, "Lahore / Remote")}${fieldIn("dates", "Dates", e.dates, "Jan 2024 - Present")}</div>
      ${bulletsIn(e.bullets, "Built X with Y, which improved Z by ~30%")}
      <div class="spread"><label class="switch"><input type="checkbox" data-f="include" ${e.include === false ? "" : "checked"}> Show on my CVs</label>${delBtn("role")}</div></div>`,
  proj: (p) => html`<div class="adv-item" data-kind="proj" data-id="${p.id || ""}">
      <div class="grid g2">${fieldIn("name", "Project name", p.name, "TaskFlow - Team Task Manager")}${fieldIn("tech", "Tech", p.tech, "Next.js, Node.js, PostgreSQL")}</div>
      ${fieldIn("url", "Link (optional)", p.url, "github.com/you/project")}
      ${bulletsIn(p.bullets, "What you built and the result")}
      <div class="row end">${delBtn("project")}</div></div>`,
  edu: (e) => html`<div class="adv-item" data-kind="edu"><div class="grid g3">
      ${fieldIn("degree", "Degree", e.degree, "BS Computer Science")}${fieldIn("school", "School", e.school, "FAST-NUCES, Lahore")}${fieldIn("dates", "Dates", e.dates, "2022 - 2026")}</div>
      <div class="row end">${delBtn("education")}</div></div>`,
};

function advancedEditor(p) {
  const sec = (title, kind, items, hint = "") => html`<div class="adv-sec">
    <div class="spread"><h3 style="margin:0">${title}</h3><button type="button" class="btn sm" data-adv-add="${kind}">+ Add</button></div>
    ${hint ? html`<p class="small muted" style="margin:4px 0 10px">${hint}</p>` : ""}
    <div data-adv-list="${kind}">${items.map((x) => ADV_ITEMS[kind](x))}</div></div>`;
  const skills = Object.entries(p.skills || {}).map(([label, items]) => ({ label, items }));
  return html`<details class="card" open><summary><b>Experience, projects, skills and education</b>
      <span class="muted small">&middot; ${p.experience?.length || 0} roles, ${p.projects?.length || 0} projects, ${Object.values(p.skills || {}).flat().length} skills</span></summary>
    <p class="small muted" style="margin-top:10px">Every fact on your CVs comes only from here, so keep it true and specific.</p>
    <div id="adv">
      ${sec("Experience", "exp", p.experience || [], "Untick \"Show on my CVs\" to keep a role saved but hidden.")}
      ${sec("Projects", "proj", p.projects || [])}
      ${sec("Skills", "skill", skills, "Grouped rows, most important first. Only skills listed here can appear on a CV.")}
      ${sec("Education", "edu", p.education || [])}
      <div class="adv-sec"><h3 style="margin:0 0 6px">Certifications <span class="muted small">(one per line)</span></h3>
        <textarea id="adv-certs" style="min-height:70px">${(p.certifications || []).join("\n")}</textarea></div>
    </div></details>`;
}

function readAdvanced(el, p) {
  const box = $("#adv", el);
  if (!box) return p;
  const val = (item, f) => ($(`[data-f="${f}"]`, item)?.value || "").trim();
  const items = (kind) => $$(`[data-adv-list="${kind}"] > .adv-item`, box);
  const slug = (s, i) => (s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "item") + (i ? `-${i}` : "");
  const byId = (list) => Object.fromEntries((list || []).map((x) => [x.id, x]));
  const oldExp = byId(p.experience), oldProj = byId(p.projects);
  const used = new Set();
  const uid = (id, base) => { let i = 0, k = id || slug(base); while (used.has(k)) k = slug(base, ++i); used.add(k); return k; };

  const experience = items("exp").map((it) => {
    const e = { title: val(it, "title"), company: val(it, "company"), location: val(it, "location"), dates: val(it, "dates"),
                bullets: splitLines(val(it, "bullets")) };
    if (!e.title && !e.company) return null;
    const id = uid(it.dataset.id, e.company || e.title);
    return { ...(oldExp[id] || {}), id, ...e, include: $('[data-f="include"]', it).checked };
  }).filter(Boolean);
  const projects = items("proj").map((it) => {
    const pr = { name: val(it, "name"), tech: val(it, "tech"), url: val(it, "url"), bullets: splitLines(val(it, "bullets")) };
    if (!pr.name) return null;
    const id = uid(it.dataset.id, pr.name);
    return { ...(oldProj[id] || {}), id, ...pr };
  }).filter(Boolean);
  const skills = {};
  items("skill").forEach((it) => {
    const label = val(it, "label") || "Skills", list = splitList(val(it, "items"));
    if (list.length) skills[label] = [...(skills[label] || []), ...list];
  });
  const education = items("edu").map((it) => ({ degree: val(it, "degree"), school: val(it, "school"), dates: val(it, "dates") }))
    .filter((e) => e.degree || e.school);
  const certifications = splitLines($("#adv-certs", box).value);
  return { ...p, experience, projects, skills, education, certifications };
}

// + Add / Remove buttons inside the editor (works wherever it is rendered)
document.addEventListener("click", (e) => {
  const add = e.target.closest("[data-adv-add]");
  if (add) {
    const list = $(`[data-adv-list="${add.dataset.advAdd}"]`, add.closest(".adv-sec"));
    list.insertAdjacentHTML("beforeend", fmt(ADV_ITEMS[add.dataset.advAdd]({})));
    $("input, textarea", list.lastElementChild)?.focus();
    return;
  }
  const del = e.target.closest("[data-adv-del]");
  if (del) del.closest(".adv-item").remove();
});

function questionInputs(questions) {
  const extra = questions.filter((q) => !CORE.includes(q.key));
  if (!extra.length) return "";
  return html`<div class="card" style="border-color:var(--accent)">
    <h2>A few things we couldn't find in your CV</h2>
    ${extra.map((q) => html`<div class="field ${q.required ? "req" : ""}"><label>${q.label}</label>
      ${q.kind === "lines" || q.kind === "textarea" ? html`<textarea data-q="${q.key}"></textarea>` : html`<input type="text" data-q="${q.key}">`}</div>`)}
  </div>`;
}

const readAnswers = (el) => Object.fromEntries($$("[data-q]", el).map((i) => [i.dataset.q, i.value]));

// ---------- onboarding ----------
async function pageOnboarding(el) {
  let profile, questions;
  const wrap = (step, body) => set(el, html`<div class="onb">
    <div class="brand" style="justify-content:center"><img src="/icons/icon-192.png" alt="">jobkit</div>
    <div class="steps">${[1, 2, 3].map((i) => html`<span class="${i <= step ? "on" : ""}"></span>`)}</div>${body}</div>`);

  let suggested = [];
  // auto-fill target roles etc. once we know something about the person (blank fields only)
  const autoSuggest = async () => {
    const knows = (profile.experience || []).length || Object.keys(profile.skills || {}).length || profile.base_summary;
    if (!knows || !SUGGESTABLE.some((k) => !profile[k] || (Array.isArray(profile[k]) && !profile[k].length))) return;
    try {
      const r = await api("POST", "/api/profile/suggest", { profile, overwrite: false });
      suggested = SUGGESTABLE.filter((k) => r.suggested[k] && JSON.stringify(profile[k] || "") !== JSON.stringify(r.profile[k]));
      ({ profile, questions } = r);
    } catch { /* suggestions are optional */ }
  };

  if (S.me.has_profile) {
    set(el, html`<div class="empty"><span class="spinner"></span> Filling in your job-search details...</div>`);
    ({ profile, questions } = await api("GET", "/api/profile"));
    await autoSuggest();
    return review();
  }
  wrap(1, html`<div class="card">
    <h1>Let's set up your job search</h1>
    <p class="muted">Upload your current CV. We'll read it, ask for anything missing, then start finding jobs that fit you.</p>
    <label class="drop" for="cv"><b>Choose your CV</b><br><span class="small muted">PDF, DOCX or TXT, up to 8 MB</span></label>
    <input id="cv" type="file" accept=".pdf,.docx,.txt,.md" class="hidden">
    <p id="st" class="small muted" style="margin-top:10px"></p>
    <div class="row" style="margin-top:8px"><button class="btn" id="manual">No CV handy? Fill it in by hand</button></div>
  </div>`);
  $("#manual", el).onclick = async () => { ({ profile, questions } = await api("GET", "/api/profile")); review(); };
  $("#cv", el).onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    set($("#st", el), html`<span class="spinner"></span> Reading ${file.name}... this takes about 20 seconds.`);
    try {
      ({ profile, questions } = await api("POST", "/api/profile/parse", { filename: file.name, data_b64: await readFileB64(file) }));
      set($("#st", el), html`<span class="spinner"></span> Suggesting job titles that fit you...`);
      await autoSuggest();
      review();
    } catch (err) { set($("#st", el), html`<span style="color:var(--bad)">${err.message}</span>`); }
  };

  function review() {
    const required = questions.filter((q) => q.required);
    wrap(2, html`<h1>Check your details</h1>
      <p class="muted">${required.length ? `We need ${required.length} more thing${required.length > 1 ? "s" : ""} (marked *) before we can search for you.` : "Looks complete. Fix anything that's wrong, then continue."}</p>
      ${suggested.length ? html`<div class="notice">✨ We suggested your ${suggested.map((k) => ({ target_roles: "target job titles", headline: "headline",
          years_experience_text: "experience", work_preferences: "work locations" }[k])).join(", ")} from your CV. Change anything that's off.</div>` : ""}
      ${questionInputs(questions)}
      <div class="card">${profileForm(profile, questions)}</div>
      ${advancedEditor(profile)}
      <div class="row end" style="margin-top:16px"><button class="btn primary" id="next" data-busy="Saving...">Continue</button></div>`);
    bindSuggest(el, () => profile);
    $("#next", el).onclick = (e) => busy(e.currentTarget, async () => {
      const p = readAdvanced(el, readProfileForm(el, profile));
      ({ profile, questions } = await api("POST", "/api/profile/answers", { profile: p, answers: readAnswers(el) }));
      const still = questions.filter((q) => q.required);
      if (still.length) { review(); toast("Still missing: " + still.map((q) => q.label).join("; "), 7000); return; }
      await api("PUT", "/api/profile", { profile });
      api("POST", "/api/scrape").catch(() => {});
      S.me = null;
      done();
    });
  }

  function done() {
    wrap(3, html`<div class="card">
      <h1>You're all set</h1>
      <p>jobkit is now scanning 15 job sources for you, and repeats that every few hours on its own.
        AI scores the best jobs against your profile, and your phone buzzes when one scores <b>90% or higher</b>.</p>
      <p class="muted small">When you like a job, tap <b>Generate</b> to get a tailored CV, cover letter, application email and recruiter messages in about a minute.</p>
      <div class="row" style="margin-top:12px">
        <button class="btn" id="push" data-busy="Enabling...">${icon("bell")} Enable notifications on this device</button>
        <button class="btn primary" id="dash">Go to my dashboard</button>
      </div>
      ${isIOS() && !standalone() ? html`<p class="small muted" style="margin-top:12px">On iPhone, first tap <b>Share</b> then <b>Add to Home Screen</b>, open jobkit from there, and enable notifications.</p>` : ""}
    </div>`);
    $("#push", el).onclick = (e) => busy(e.currentTarget, async () => { await enablePush(); toast("Notifications on for this device"); });
    $("#dash", el).onclick = () => go("#/");
  }
}

// ---------- overview ----------
async function pageOverview(el) {
  const o = await api("GET", "/api/overview");
  const k = o.kpis;
  const ch = S.me.channels || {};
  const total = Object.values(o.by_status).reduce((a, b) => a + b, 0);
  const src = Object.entries(o.by_source).sort((a, b) => b[1] - a[1]).slice(0, 10);
  const maxSrc = Math.max(1, ...src.map((s) => s[1]));
  set(el, html`
    <div class="page-head"><div><h1>Hi ${S.me.uid}</h1>
      <div class="muted small">Last scan ${ago(o.last_run)}${o.watcher.next_run ? ` · next ${ago(o.watcher.next_run)}` : ""}</div></div>
      <button class="btn" id="scrape" data-busy="Starting...">${icon("refresh")} Scan now</button></div>
    ${!ch.web_push_devices && !ch.ntfy && !ch.telegram ? html`<div class="notice">Turn on notifications so you hear about ${o.threshold}%+ matches right away. <a href="#/settings">Set up</a></div>` : ""}
    ${!S.me.ai ? html`<div class="notice warn">AI scoring and tailoring are off because the server has no ANTHROPIC_API_KEY. Jobs are ranked by keywords only.</div>` : ""}
    <div id="live"></div>
    <div class="kpis">
      <a class="kpi hi" href="#/jobs?view=strong"><div class="v">${k.strong}</div><div class="l">Strong matches (${o.threshold}%+)</div></a>
      <a class="kpi" href="#/jobs?view=new"><div class="v">${k.new}</div><div class="l">New since last scan</div></a>
      <a class="kpi" href="#/jobs"><div class="v">${k.matched}</div><div class="l">Matching jobs</div></a>
      <a class="kpi" href="#/jobs?view=shortlisted"><div class="v">${k.shortlisted}</div><div class="l">Shortlisted</div></a>
      <a class="kpi" href="#/applications"><div class="v">${k.active}</div><div class="l">Active applications</div></a>
      <a class="kpi" href="#/applications?status=interviewing"><div class="v">${k.interviews}</div><div class="l">Interviews</div></a>
      <a class="kpi" href="#/applications?status=offer"><div class="v">${k.offers}</div><div class="l">Offers</div></a>
    </div>
    <div class="grid g2">
      <div class="card"><div class="spread"><h2>Best matches right now</h2><a class="small" href="#/jobs">All jobs</a></div>
        ${o.top.length ? html`<div class="list">${o.top.map((r) => jobItem(r, false))}</div>`
          : html`<div class="empty">No matches yet. ${o.watcher.running ? "A scan is running now." : "Run a scan to fetch jobs."}</div>`}</div>
      <div class="grid" style="align-content:start">
        <div class="card"><h2>Follow-ups due</h2>
          ${o.followups.length ? html`<div class="list">${o.followups.map((a) => html`<div class="item"><div class="body">
              <div class="title">${a.role}</div><div class="meta">${a.company} · applied ${a.applied_on}</div></div>
              <div class="acts"><a class="btn sm primary" href="#/outreach?app=${a.id}&kind=follow_up">Write follow-up</a></div></div>`)}</div>`
            : html`<p class="muted small">Nothing due. Applications get a follow-up reminder 7 days after you apply.</p>`}</div>
        <div class="card"><h2>Pipeline</h2>
          ${total ? html`<div class="bar" role="img" aria-label="Applications by status">${Object.entries(o.by_status).filter(([, v]) => v).map(([s, v]) =>
              html`<span style="width:${(v / total) * 100}%;background:${STATUS_COLORS[s]}" title="${s}: ${v}"></span>`)}</div>
            <div class="legend">${Object.entries(o.by_status).filter(([, v]) => v).map(([s, v]) => html`<span><i style="background:${STATUS_COLORS[s]}"></i>${s} ${v}</span>`)}</div>`
            : html`<p class="muted small">No applications yet. Open a job and hit <b>Generate</b>.</p>`}</div>
        <div class="card"><h2>Where your matches come from</h2>
          ${src.length ? src.map(([s, v]) => html`<div class="hbar"><span>${s}</span><div class="track"><div class="fill" style="width:${(v / maxSrc) * 100}%"></div></div><span class="n">${v}</span></div>`)
            : html`<p class="muted small">Run a scan to see sources.</p>`}
          ${Object.keys(o.sources).length ? html`<details style="margin-top:8px"><summary class="small muted">Source health from the last scan</summary>
            <table><tr><th>Source</th><th>Fetched</th><th>Status</th></tr>${Object.entries(o.sources).map(([n, s]) =>
              html`<tr><td>${n}</td><td>${s.fetched}</td><td class="small ${s.status === "ok" ? "" : "muted"}">${s.status}</td></tr>`)}</table></details>` : ""}
        </div>
      </div>
    </div>`);
  const live = $("#live", el);
  const watch = () => {
    S.poll = setInterval(async () => {
      const st = await api("GET", "/api/scrape/status").catch(() => null);
      if (!st) return;
      set(live, html`<div class="card" style="margin-bottom:16px"><div class="spread"><h2>${st.running ? html`<span class="spinner"></span> Scanning job sources...` : "Scan finished"}</h2>
        ${st.running ? "" : html`<button class="btn sm" id="reload">Refresh results</button>`}</div>
        <div class="log">${st.log.join("\n")}</div></div>`);
      const lg = $(".log", live); lg.scrollTop = lg.scrollHeight;
      if (!st.running) { clearInterval(S.poll); $("#reload", live).onclick = () => route(); }
    }, 2500);
  };
  if (o.watcher.running) watch();
  $("#scrape", el).onclick = (e) => busy(e.currentTarget, async () => {
    const r = await api("POST", "/api/scrape");
    toast(r.started ? `Started: ${r.mode}` : "A scan is already running");
    clearInterval(S.poll); watch();
  });
}

// ---------- jobs ----------
async function pageJobs(el, m, q) {
  const rows = await api("GET", "/api/jobs");
  const thr = S.me.threshold || 90;
  const f = { text: "", view: q.get("view") || store.get("jobs.view", "all"), source: "", sort: store.get("jobs.sort", "best"), limit: 60 };
  const sources = [...new Set(rows.map((r) => r.source.split("/")[0]))].sort();
  const views = [["all", "All"], ["strong", `${thr}%+`], ["new", "New"], ["shortlisted", "Shortlisted"], ["scored", "AI-scored"], ["hidden", "Hidden"]];
  set(el, html`
    <div class="page-head"><div><h1>Jobs</h1><div class="muted small">${rows.length} jobs matched your keywords. Open one to see the AI fit and generate your application.</div></div>
      <a class="btn" href="#/apply">Tailor for a job not listed</a></div>
    <div class="card" style="margin-bottom:16px">
      <div class="grid g3" style="align-items:end">
        <div><label for="t">Search</label><input id="t" type="search" placeholder="title, company, skill, location"></div>
        <div><label for="src">Source</label><select id="src"><option value="">All sources</option>${sources.map((s) => html`<option>${s}</option>`)}</select></div>
        <div><label for="sort">Sort</label><select id="sort">
          <option value="best">Best match</option><option value="new">Newest</option><option value="kw">Keyword score</option></select></div>
      </div>
      <div class="chips" style="margin-top:12px" id="views">${views.map(([v, l]) => html`<button class="chip" data-v="${v}">${l}</button>`)}</div>
    </div>
    <div class="card"><div class="list" id="list"></div><div class="row" style="justify-content:center;margin-top:10px"><button class="btn hidden" id="more">Show more</button></div></div>`);
  $("#sort", el).value = f.sort;
  const best = (r) => (r.ai_match != null ? 1000 + r.ai_match : r.score);
  const draw = () => {
    $$("#views .chip", el).forEach((c) => c.classList.toggle("on", c.dataset.v === f.view));
    const t = f.text.toLowerCase();
    const list = rows.filter((r) => (f.view === "hidden" ? r.state === "hidden" : r.state !== "hidden"))
      .filter((r) => f.view !== "strong" || (r.ai_match ?? 0) >= thr)
      .filter((r) => f.view !== "new" || r.new)
      .filter((r) => f.view !== "shortlisted" || r.state === "shortlisted")
      .filter((r) => f.view !== "scored" || r.ai_match != null)
      .filter((r) => !f.source || r.source.startsWith(f.source))
      .filter((r) => !t || `${r.title} ${r.company} ${r.location} ${r.why}`.toLowerCase().includes(t));
    list.sort(f.sort === "new" ? (a, b) => (b.date || "").localeCompare(a.date || "") : f.sort === "kw" ? (a, b) => b.score - a.score : (a, b) => best(b) - best(a));
    set($("#list", el), list.length ? list.slice(0, f.limit).map((r) => jobItem(r)) : html`<div class="empty">No jobs here. Try another filter${rows.length ? "" : ", or run a scan from Overview"}.</div>`);
    $("#more", el).classList.toggle("hidden", list.length <= f.limit);
    bindJobActions(el, rows, draw);
  };
  $("#t", el).oninput = (e) => { f.text = e.target.value; f.limit = 60; draw(); };
  $("#src", el).onchange = (e) => { f.source = e.target.value; draw(); };
  $("#sort", el).onchange = (e) => { f.sort = e.target.value; store.set("jobs.sort", f.sort); draw(); };
  $$("#views .chip", el).forEach((c) => (c.onclick = () => { f.view = c.dataset.v; store.set("jobs.view", f.view); f.limit = 60; draw(); }));
  $("#more", el).onclick = () => { f.limit += 60; draw(); };
  draw();
}

async function pageJob(el, m) {
  const [j] = await Promise.all([api("GET", `/api/jobs/${m[1]}`), loadThemes()]);
  const [skills, flags] = String(j.why || "").split(" | ");
  const draw = () => {
    set(el, html`
    <p><a href="#/jobs" class="small">&larr; Jobs</a></p>
    <div class="card">
      <div class="item" style="padding:0">${scoreBox(j)}
        <div class="body"><h1>${j.title}</h1>
          <div class="muted">${j.company || "Unknown company"} &middot; ${j.location || "Location n/a"} &middot; ${j.source}${j.date ? ` · posted ${j.date}` : ""}</div>
          <div class="chips" style="margin-top:8px">${j.new ? html`<span class="badge acc">New</span>` : ""}
            ${(flags || "").split(" ").filter(Boolean).map((x) => html`<span class="badge warn">${x}</span>`)}
            ${j.state ? html`<span class="badge good">${j.state}</span>` : ""}</div></div></div>
      <div class="row" style="margin-top:16px">
        ${themeSelect("theme", S.me.cv_theme)}
        <button class="btn primary" id="apply" data-busy="Tailoring your CV, letter and emails (about 40s)...">${icon("file")} Generate CV + cover letter + emails</button>
        ${j.ai_match == null && S.me.ai ? html`<button class="btn" id="score" data-busy="Scoring...">Get AI match score</button>` : ""}
        ${j.url ? html`<a class="btn" href="${j.url}" target="_blank" rel="noopener noreferrer">${icon("ext")} Open posting</a>` : ""}
        <button class="btn" id="star">${icon("star")} ${j.state === "shortlisted" ? "Shortlisted" : "Shortlist"}</button>
        <button class="btn" id="hide">${icon("hide")} ${j.state === "hidden" ? "Unhide" : "Hide"}</button>
      </div>
    </div>
    ${j.ai_match != null ? html`<div class="card"><h2>AI fit: ${j.ai_match}%</h2><p>${j.ai_verdict}</p>
      <div class="grid g2">
        <div><h3 style="color:var(--good)">Strengths</h3><ul>${(j.ai_strengths || []).map((s) => html`<li>${s}</li>`)}</ul></div>
        <div><h3 style="color:var(--warn)">Gaps</h3><ul>${(j.ai_gaps || []).map((s) => html`<li>${s}</li>`)}</ul></div>
      </div></div>` : ""}
    ${skills ? html`<div class="card"><h2>Your skills it mentions</h2><div class="chips">${skills.split(", ").map((s) => html`<span class="badge acc">${s}</span>`)}</div></div>` : ""}
    <div class="card"><h2>Job description</h2><div class="desc">${j.desc || "No description was available from this source. Open the posting to read it."}</div></div>`);
    $("#apply", el).onclick = (e) => busy(e.currentTarget, async () => {
      const r = await api("POST", `/api/jobs/${j.key}/apply`, { theme: $("#theme", el).value });
      go(`#/apply/${encodeURIComponent(r.folder)}`);
    });
    const sc = $("#score", el);
    if (sc) sc.onclick = (e) => busy(e.currentTarget, async () => {
      const r = await api("POST", `/api/jobs/${j.key}/score`);
      Object.assign(j, { ai_match: r.match, ai_verdict: r.verdict, ai_strengths: r.strengths, ai_gaps: r.gaps });
      draw();
    });
    $("#star", el).onclick = async () => { j.state = j.state === "shortlisted" ? "" : "shortlisted"; await api("POST", `/api/jobs/${j.key}/state`, { state: j.state }); draw(); };
    $("#hide", el).onclick = async () => { j.state = j.state === "hidden" ? "" : "hidden"; await api("POST", `/api/jobs/${j.key}/state`, { state: j.state }); draw(); };
  };
  draw();
}

// ---------- apply + package ----------
async function pageApply(el) {
  const [apps] = await Promise.all([api("GET", "/api/applications"), loadThemes()]);
  const recent = apps.rows.filter((a) => a.folder).slice(-6).reverse();
  set(el, html`
    <div class="page-head"><div><h1>Tailor and apply</h1><div class="muted small">Paste any job. You get a tailored one-page CV, cover letter, application email and gap report.</div></div></div>
    <div class="grid g2">
      <div class="card">
        <div class="field"><label for="jd">Job description</label><textarea id="jd" class="tall" placeholder="Paste the full job description here"></textarea></div>
        <div class="field"><label for="url">...or a public job URL <span class="muted">(LinkedIn often blocks this; pasting is more reliable)</span></label><input id="url" type="url" placeholder="https://"></div>
        <div class="grid g2"><div class="field"><label for="co">Company <span class="muted">(optional)</span></label><input id="co" type="text"></div>
          <div class="field"><label for="theme">CV design</label>${themeSelect("theme", S.me.cv_theme)}</div></div>
        <button class="btn primary" id="go" data-busy="Tailoring (about 40s)...">${icon("file")} Generate application</button>
      </div>
      <div class="grid" style="align-content:start">
        <div class="card"><h2>How it stays honest</h2><ul class="small">
          <li>Only facts from your profile and GitHub are used. The AI selects, orders and rewords them to match the job.</li>
          <li>Skills you don't have are never added; they show up as <b>gaps</b> for you to review.</li>
          <li>Every PDF is a single column with real text, so applicant tracking systems read it cleanly.</li>
          <li>Always read the letter and email before you send them.</li></ul></div>
        <div class="card"><h2>Recent</h2>${recent.length ? html`<div class="list">${recent.map((a) => html`<div class="item"><div class="body">
          <a class="title" href="#/apply/${encodeURIComponent(a.folder)}">${a.role}</a><div class="meta">${a.company} · ${a.date} · ${a.status}</div></div></div>`)}</div>`
          : html`<p class="muted small">Nothing yet.</p>`}</div>
      </div>
    </div>`);
  $("#go", el).onclick = (e) => busy(e.currentTarget, async () => {
    const r = await api("POST", "/api/apply", { jd: $("#jd", el).value, url: $("#url", el).value, company: $("#co", el).value, theme: $("#theme", el).value });
    go(`#/apply/${encodeURIComponent(r.folder)}`);
  });
}

async function pagePackage(el, m) {
  const name = decodeURIComponent(m[1]);
  const [pkg, apps] = await Promise.all([api("GET", `/api/packages/${encodeURIComponent(name)}`), api("GET", "/api/applications"), loadThemes()]);
  const app = apps.rows.find((a) => a.folder === name);
  let c = pkg.tailored, tab = "cv", bust = Date.now();
  const file = (f, dl) => `/api/packages/${encodeURIComponent(name)}/files/${f}?t=${bust}${dl ? "&download=1" : ""}`;
  const rebuild = async (edits, theme) => {
    const r = await api("POST", `/api/packages/${encodeURIComponent(name)}/render`, { edits, theme });
    c = r.tailored; bust = Date.now(); toast("Saved and PDFs rebuilt"); draw();
  };
  const pdf = (f, label) => html`<iframe class="pdf" src="${file(f)}" title="${label} preview"></iframe>
    <div class="row" style="margin-top:8px"><a class="btn primary" href="${file(f, 1)}">Download ${label}</a><a class="btn" href="${file(f)}" target="_blank" rel="noopener">Open full screen</a></div>`;

  function body() {
    if (tab === "cv") return html`<div class="chips" style="margin-bottom:12px">${S.themes.map((t) =>
        html`<button class="chip ${t.id === c.theme ? "on" : ""}" data-theme="${t.id}">${t.label.split(" - ")[0]}</button>`)}</div>
      <div class="grid g2"><div>
        <div class="field"><label>Headline</label><input id="hl" type="text" value="${c.headline}"></div>
        <div class="field"><label>Summary</label><textarea id="sm">${c.summary}</textarea></div>
        <h3>Experience bullets</h3>
        ${c.experience.map((x, i) => html`<div class="field"><label class="muted">${x.id}</label><textarea data-exp="${i}">${x.bullets.join("\n")}</textarea></div>`)}
        <button class="btn primary" id="savecv" data-busy="Rebuilding...">Save and rebuild PDF</button>
        <p class="small muted">One bullet per line. Keep numbers true; edits are checked against your profile.</p>
      </div><div>${pdf("CV.pdf", "CV")}</div></div>`;
    if (tab === "letter") return html`<div class="grid g2"><div>
        <textarea id="cl" class="tall">${c.cover_letter}</textarea>
        <div class="row" style="margin-top:8px"><button class="btn primary" id="savecl" data-busy="Rebuilding...">Save and rebuild PDF</button>
          <button class="btn" id="copycl">Copy text</button></div></div>
      <div>${pdf("Cover_Letter.pdf", "cover letter")}</div></div>`;
    if (tab === "email") return html`<div class="field"><label>To <span class="muted">(recruiter email, saved to the tracker)</span></label><input id="to" type="email" value="${app?.contact_email || ""}" placeholder="recruiter@company.com"></div>
        <div class="field"><label>Subject</label><input id="subj" type="text" value="${c.email_subject}"></div>
        <div class="field"><label>Body</label><textarea id="eb" class="tall">${c.email_body}</textarea></div>
        <div class="row"><button class="btn" id="cps">Copy subject</button><button class="btn" id="cpb">Copy body</button>
          <a class="btn primary" id="mailto" href="#">${icon("mail")} Open in email app</a>
          <button class="btn" id="saveem" data-busy="Saving...">Save</button></div>
        <p class="small muted">Remember to attach CV.pdf and Cover_Letter.pdf (download them from the other tabs).</p>`;
    if (tab === "outreach") return html`<p class="muted small">Recruiter and referral messages for this application. Find the recruiter on LinkedIn by searching "${c.company} recruiter" or "talent acquisition", and the hiring manager with "engineering manager ${c.company}".</p>
      <div class="grid g2"><div class="field"><label>Recipient name <span class="muted">(optional)</span></label><input id="rcp" type="text" value="${app?.contact || ""}"></div>
        <div class="field"><label>Anything to mention? <span class="muted">(optional)</span></label><input id="nts" type="text"></div></div>
      <div class="row">${Object.entries(KINDS).map(([k, l]) => html`<button class="btn sm" data-kind="${k}" data-busy="Writing...">${l}</button>`)}</div>
      <div id="out" style="margin-top:16px"></div>`;
    return html`<div class="desc">${pkg.jd || "Not saved."}</div>`;
  }

  function draw() {
    set(el, html`<p><a href="#/applications" class="small">&larr; Applications</a></p>
      <div class="page-head"><div><h1>${c.role}</h1><div class="muted">${c.company} &middot; tailored match ${c.match_score}/100</div></div>
        ${app ? html`<div class="row"><label for="status" class="small muted" style="margin:0">Status</label>
          <select id="status" style="width:auto">${apps.statuses.map((s) => html`<option ${s === app.status ? "selected" : ""}>${s}</option>`)}</select></div>` : ""}</div>
      ${c.gaps?.length ? html`<div class="notice warn"><b>Check before sending:</b><ul style="margin:6px 0 0">${c.gaps.map((g) => html`<li>${g}</li>`)}</ul></div>` : ""}
      ${c.keywords_matched?.length ? html`<div class="chips" style="margin-bottom:16px">${c.keywords_matched.map((k) => html`<span class="badge acc">${k}</span>`)}</div>` : ""}
      <div class="card"><div class="tabs">${[["cv", "CV"], ["letter", "Cover letter"], ["email", "Application email"], ["outreach", "Recruiter outreach"], ["jd", "Job description"]].map(([t, l]) =>
        html`<button class="${t === tab ? "on" : ""}" data-tab="${t}">${l}</button>`)}</div>${body()}</div>`);
    bind();
  }

  function bind() {
    $$("[data-tab]", el).forEach((b) => (b.onclick = () => { tab = b.dataset.tab; draw(); }));
    const st = $("#status", el);
    if (st) st.onchange = async () => { Object.assign(app, await api("PATCH", `/api/applications/${app.id}`, { status: st.value })); toast(`Marked ${st.value}`); };
    $$("[data-theme]", el).forEach((b) => (b.onclick = () => busy(b, () => rebuild({}, b.dataset.theme))));
    const sv = $("#savecv", el);
    if (sv) sv.onclick = () => busy(sv, () => {
      const exp = c.experience.map((x, i) => ({ ...x, bullets: splitLines($(`[data-exp="${i}"]`, el).value) }));
      return rebuild({ headline: $("#hl", el).value, summary: $("#sm", el).value, experience: exp });
    });
    const scl = $("#savecl", el);
    if (scl) { scl.onclick = () => busy(scl, () => rebuild({ cover_letter: $("#cl", el).value })); $("#copycl", el).onclick = () => copy($("#cl", el).value); }
    if ($("#eb", el)) {
      $("#cps", el).onclick = () => copy($("#subj", el).value);
      $("#cpb", el).onclick = () => copy($("#eb", el).value);
      $("#mailto", el).onclick = (e) => { e.preventDefault(); location.href = `mailto:${encodeURIComponent($("#to", el).value)}?subject=${encodeURIComponent($("#subj", el).value)}&body=${encodeURIComponent($("#eb", el).value)}`; };
      $("#saveem", el).onclick = (e) => busy(e.currentTarget, async () => {
        if (app && $("#to", el).value !== app.contact_email) Object.assign(app, await api("PATCH", `/api/applications/${app.id}`, { contact_email: $("#to", el).value }));
        await rebuild({ email_subject: $("#subj", el).value, email_body: $("#eb", el).value });
      });
    }
    $$("[data-kind]", el).forEach((b) => (b.onclick = () => busy(b, async () => {
      const r = await api("POST", "/api/outreach", { kind: b.dataset.kind, app_id: app?.id, company: c.company, role: c.role, recipient: $("#rcp", el).value, notes: $("#nts", el).value });
      showMessage($("#out", el), b.dataset.kind, r, app?.contact_email);
    })));
  }
  draw();
}

function showMessage(box, kind, r, to = "") {
  set(box, html`<div class="card" style="background:var(--panel-2)">
    <div class="spread"><h3>${KINDS[kind]}</h3><span class="small muted" id="mlen">${r.body.length} characters${kind === "linkedin_note" ? " / 300" : ""}</span></div>
    ${r.subject ? html`<div class="field"><label>Subject</label><input type="text" id="msubj" value="${r.subject}"></div>` : ""}
    <textarea id="mbody" class="tall">${r.body}</textarea>
    <div class="row" style="margin-top:8px">${r.subject ? html`<button class="btn" id="mcs">Copy subject</button>` : ""}<button class="btn primary" id="mcb">Copy message</button>
      ${r.subject ? html`<a class="btn" id="mmail" href="#">${icon("mail")} Open in email app</a>` : ""}</div></div>`);
  $("#mbody", box).oninput = (e) => ($("#mlen", box).textContent = `${e.target.value.length} characters${kind === "linkedin_note" ? " / 300" : ""}`);
  $("#mcb", box).onclick = () => copy($("#mbody", box).value);
  if (r.subject) {
    $("#mcs", box).onclick = () => copy($("#msubj", box).value);
    $("#mmail", box).onclick = (e) => { e.preventDefault(); location.href = `mailto:${encodeURIComponent(to || "")}?subject=${encodeURIComponent($("#msubj", box).value)}&body=${encodeURIComponent($("#mbody", box).value)}`; };
  }
}

// ---------- applications ----------
async function pageApplications(el, m, q) {
  const { rows, statuses } = await api("GET", "/api/applications");
  let filter = q.get("status") || "all";
  const today = new Date().toISOString().slice(0, 10);
  const draw = () => {
    const list = rows.filter((r) => filter === "all" || r.status === filter).slice().reverse();
    set(el, html`<div class="page-head"><div><h1>Applications</h1><div class="muted small">Change a status and it saves. Marking "applied" schedules a follow-up reminder 7 days later.</div></div></div>
      <div class="chips" style="margin-bottom:16px">
        <button class="chip ${filter === "all" ? "on" : ""}" data-f="all">All ${rows.length}</button>
        ${statuses.map((s) => html`<button class="chip ${filter === s ? "on" : ""}" data-f="${s}"><i style="width:8px;height:8px;border-radius:50%;background:${STATUS_COLORS[s]};display:inline-block"></i>${s} ${rows.filter((r) => r.status === s).length}</button>`)}</div>
      <div class="card">${list.length ? html`<div class="list">${list.map((r) => {
        const due = ["applied", "follow-up sent"].includes(r.status) && r.follow_up && r.follow_up <= today;
        return html`<div class="item" data-id="${r.id}"><div class="body">
          <div class="spread"><div>${r.folder ? html`<a class="title" href="#/apply/${encodeURIComponent(r.folder)}">${r.role}</a>` : html`<span class="title">${r.role}</span>`}
            <div class="meta">${r.company}${r.match ? ` · match ${r.match}` : ""} · created ${r.date}${r.applied_on ? ` · applied ${r.applied_on}` : ""}</div></div>
            <select data-k="status" style="width:auto" aria-label="Status">${statuses.map((s) => html`<option ${s === r.status ? "selected" : ""}>${s}</option>`)}</select></div>
          ${due ? html`<div class="notice warn small" style="margin:8px 0 0">Follow-up due (${r.follow_up}). <a href="#/outreach?app=${r.id}&kind=follow_up">Write it now</a></div>` : ""}
          <details style="margin-top:8px"><summary class="small muted">Contact, dates and notes</summary>
            <div class="grid g2" style="margin-top:8px">
              <div class="field"><label>Recruiter / contact</label><input type="text" data-k="contact" value="${r.contact}"></div>
              <div class="field"><label>Contact email</label><input type="email" data-k="contact_email" value="${r.contact_email}"></div>
              <div class="field"><label>Applied on</label><input type="date" data-k="applied_on" value="${r.applied_on}"></div>
              <div class="field"><label>Follow up on</label><input type="date" data-k="follow_up" value="${r.follow_up}"></div></div>
            <div class="field"><label>Notes</label><input type="text" data-k="notes" value="${r.notes}"></div>
            <div class="row"><a class="btn sm" href="#/outreach?app=${r.id}">${icon("mail")} Write a message</a>
              ${r.job_url ? html`<a class="btn sm" href="${r.job_url}" target="_blank" rel="noopener noreferrer">${icon("ext")} Job posting</a>` : ""}</div>
          </details></div></div>`;
      })}</div>` : html`<div class="empty">No applications${filter === "all" ? " yet. Pick a job and hit Generate" : ` with status "${filter}"`}.</div>`}</div>`);
    $$("[data-f]", el).forEach((b) => (b.onclick = () => { filter = b.dataset.f; draw(); }));
    $$("[data-k]", el).forEach((i) => (i.onchange = async () => {
      const id = i.closest("[data-id]").dataset.id;
      try {
        const r = await api("PATCH", `/api/applications/${id}`, { [i.dataset.k]: i.value });
        Object.assign(rows.find((x) => x.id === id), r);
        toast("Saved");
        if (i.dataset.k === "status") draw();
      } catch (e) { toast(e.message); }
    }));
  };
  draw();
}

// ---------- outreach ----------
async function pageOutreach(el, m, q) {
  const { rows } = await api("GET", "/api/applications");
  set(el, html`<div class="page-head"><div><h1>Recruiter outreach</h1><div class="muted small">Short, specific messages built only from your real experience.</div></div></div>
    <div class="grid g2"><div class="card">
      <div class="field"><label for="kind">Message type</label><select id="kind">${Object.entries(KINDS).map(([k, l]) => html`<option value="${k}">${l}</option>`)}</select></div>
      <div class="field"><label for="app">For application <span class="muted">(optional, fills in company, role and job description)</span></label>
        <select id="app"><option value="">None</option>${rows.slice().reverse().map((r) => html`<option value="${r.id}">${r.role} @ ${r.company}</option>`)}</select></div>
      <div class="grid g2"><div class="field"><label for="co">Company</label><input id="co" type="text"></div>
        <div class="field"><label for="ro">Role</label><input id="ro" type="text"></div></div>
      <div class="field"><label for="rc">Recipient name <span class="muted">(optional)</span></label><input id="rc" type="text"></div>
      <div class="field"><label for="nt">Anything to mention? <span class="muted">(optional)</span></label><input id="nt" type="text" placeholder="e.g. met them at a meetup, liked their talk on..."></div>
      <details><summary class="small">Paste the job description (optional)</summary><textarea id="jd" style="margin-top:8px"></textarea></details>
      <button class="btn primary" id="go" style="margin-top:12px" data-busy="Writing...">${icon("mail")} Write message</button>
      <div id="out" style="margin-top:16px"></div>
    </div>
    <div class="card"><h2>Playbook</h2><ol class="small">
      <li><b>Apply first</b>, then message within 24 hours. Mention that you applied.</li>
      <li><b>Find the right person:</b> on LinkedIn search "<i>company</i> recruiter", "talent acquisition", or the hiring manager ("engineering manager <i>company</i>").</li>
      <li><b>Connection note</b> (300 chars) to the recruiter, then a <b>message</b> once they accept.</li>
      <li><b>Referrals</b> are the strongest channel: message an engineer on the team with the referral template.</li>
      <li><b>Follow up</b> after 7 days if there's no reply, at most twice in total.</li>
      <li>After every interview, send the <b>thank-you</b> within 24 hours.</li></ol></div></div>`);
  const appSel = $("#app", el);
  const fill = () => { const r = rows.find((x) => x.id === appSel.value); if (r) { $("#co", el).value = r.company; $("#ro", el).value = r.role; $("#rc", el).value = r.contact || ""; } };
  if (q.get("app")) { appSel.value = q.get("app"); fill(); }
  if (q.get("kind")) $("#kind", el).value = q.get("kind");
  appSel.onchange = fill;
  $("#go", el).onclick = (e) => busy(e.currentTarget, async () => {
    const kind = $("#kind", el).value;
    const r = await api("POST", "/api/outreach", { kind, app_id: appSel.value || null, company: $("#co", el).value, role: $("#ro", el).value,
      recipient: $("#rc", el).value, notes: $("#nt", el).value, jd: $("#jd", el).value });
    showMessage($("#out", el), kind, r, rows.find((x) => x.id === appSel.value)?.contact_email);
  });
}

// ---------- profile + CV designs + GitHub ----------
async function pageProfile(el, m, q) {
  const [{ profile, questions }, themes, st, gh] = await Promise.all([api("GET", "/api/profile"), loadThemes(), api("GET", "/api/settings"), api("GET", "/api/github")]);
  let p = profile, qs = questions, tab = q.get("tab") || "details";
  const draw = () => {
    set(el, html`<div class="page-head"><div><h1>Profile and CV</h1><div class="muted small">Everything on your CVs comes from here.</div></div></div>
      <div class="tabs">${[["details", "Details"], ["designs", "CV designs"], ["github", "GitHub projects"]].map(([t, l]) => html`<button class="${t === tab ? "on" : ""}" data-tab="${t}">${l}</button>`)}</div>
      <div id="body"></div>`);
    $$("[data-tab]", el).forEach((b) => (b.onclick = () => { tab = b.dataset.tab; draw(); }));
    const body = $("#body", el);
    if (tab === "details") {
      set(body, html`${qs.length ? html`<div class="notice">Missing: ${qs.map((x) => x.label).join("; ")}</div>` : ""}
        ${questionInputs(qs)}
        <div class="card">${profileForm(p, qs)}</div>${advancedEditor(p)}
        <div class="card"><div class="spread"><label class="switch"><input type="checkbox" id="rb"> Also rebuild my job-search keywords from this profile</label>
          <div class="row"><label class="btn" for="recv" style="margin:0">Re-import from a new CV</label><input id="recv" type="file" accept=".pdf,.docx,.txt,.md" class="hidden">
          <button class="btn primary" id="save" data-busy="Saving...">Save profile</button></div></div></div>`);
      bindSuggest(body, () => p);
      $("#save", body).onclick = (e) => busy(e.currentTarget, async () => {
        let np = readAdvanced(body, readProfileForm(body, p));
        if ($$("[data-q]", body).length) np = (await api("POST", "/api/profile/answers", { profile: np, answers: readAnswers(body) })).profile;
        const r = await api("PUT", "/api/profile", { profile: np, rebuild_search: $("#rb", body).checked });
        p = r.profile; qs = r.questions; S.me = null; toast("Profile saved"); draw();
      });
      $("#recv", body).onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        toast("Reading your CV (about 20s)...", 20000);
        try {
          const r = await api("POST", "/api/profile/parse", { filename: file.name, data_b64: await readFileB64(file) });
          p = r.profile; qs = r.questions; draw();
          toast("Imported. Review it, then press Save profile.");
        } catch (err) { toast(err.message, 6000); }
      };
    } else if (tab === "designs") {
      const cur = st.config.cv_theme;
      set(body, html`<p class="muted">Pick the default design for new applications. All of them are single-column and ATS-safe; you can switch per application too.</p>
        <div class="grid g2">${themes.map((t) => html`<div class="theme-card ${t.id === cur ? "on" : ""}">
          <div class="swatch"><b style="background:${t.accent}"></b><u style="background:${t.accent}"></u><i style="width:90%"></i><i style="width:75%"></i><i style="width:82%"></i></div>
          <div><b>${t.label.split(" - ")[0]}</b> <span class="muted small">${t.label.split(" - ")[1] || ""}</span></div>
          <div class="row"><a class="btn sm" href="/api/cv/base/${t.id}" target="_blank" rel="noopener">Preview with my profile</a>
            ${t.id === cur ? html`<span class="badge good">Default</span>` : html`<button class="btn sm" data-use="${t.id}">Use as default</button>`}</div></div>`)}</div>`);
      $$("[data-use]", body).forEach((b) => (b.onclick = async () => {
        st.config = (await api("PUT", "/api/settings", { config: { cv_theme: b.dataset.use } })).config;
        S.me = null; toast("Default design updated"); draw();
      }));
    } else {
      set(body, html`<div class="card"><div class="grid g2" style="align-items:end">
          <div><label for="ghu">GitHub username</label><input id="ghu" type="text" value="${st.config.github_user}"></div>
          <div class="row"><button class="btn" id="ghsave">Save</button><button class="btn primary" id="ghsync" data-busy="Syncing (up to a minute)...">${icon("refresh")} Sync repos</button></div></div>
        <p class="small muted">We read each repo's description, topics, languages and README so tailored CVs can cite real projects. Untick anything you don't want used. Better READMEs make better CV bullets.</p></div>
        <div class="card">${gh.repos.length ? html`<div class="list">${gh.repos.map((r) => html`<div class="item"><div class="body">
            <a class="title" href="${r.url}" target="_blank" rel="noopener noreferrer">${r.name}</a>
            <div class="meta">${r.description || "No description"} · ${(r.languages || []).join(", ")}${r.stars ? ` · ★ ${r.stars}` : ""}</div></div>
            <label class="switch"><input type="checkbox" data-repo="${r.name}" ${r.include !== false ? "checked" : ""}> Use</label></div>`)}</div>`
          : html`<div class="empty">No repos synced yet.</div>`}</div>`);
      $("#ghsave", body).onclick = async () => { st.config = (await api("PUT", "/api/settings", { config: { github_user: $("#ghu", body).value.trim() } })).config; toast("Saved"); };
      $("#ghsync", body).onclick = (e) => busy(e.currentTarget, async () => {
        await api("PUT", "/api/settings", { config: { github_user: $("#ghu", body).value.trim() } });
        gh.repos = (await api("POST", "/api/github/sync")).repos; toast(`Synced ${gh.repos.length} repos`); draw();
      });
      $$("[data-repo]", body).forEach((c) => (c.onchange = () => api("POST", `/api/github/${encodeURIComponent(c.dataset.repo)}`, { include: c.checked }).then(() => toast("Saved"))));
    }
  };
  draw();
}

// ---------- settings ----------
const SOURCE_INFO = {
  remotive: "Remotive (remote)", remoteok: "RemoteOK (remote)", arbeitnow: "Arbeitnow (remote, EU-heavy)", himalayas: "Himalayas (remote)",
  jobicy: "Jobicy (remote)", weworkremotely: "We Work Remotely", workingnomads: "Working Nomads (remote)", hackernews: "Hacker News: Who is hiring",
  greenhouse: "Greenhouse company boards", lever: "Lever company boards", ashby: "Ashby company boards", linkedin: "LinkedIn public listings",
  adzuna: "Adzuna (needs server key)", jsearch: "JSearch: Indeed, Glassdoor, LinkedIn via Google Jobs (needs server key)",
  jobspy: "JobSpy: Indeed, Glassdoor, Google, ZipRecruiter (needs package on server)",
};

async function pageSettings(el) {
  const s = await api("GET", "/api/settings");
  const c = s.config, ch = s.channels;
  const list = (k, label, hint = "") => html`<div class="field"><label for="c-${k}">${label} ${hint ? html`<span class="muted">${hint}</span>` : ""}</label><textarea id="c-${k}" data-list="${k}" style="min-height:70px">${c[k].join(", ")}</textarea></div>`;
  const num = (k, label, min, max) => html`<div class="field"><label for="c-${k}">${label}</label><input id="c-${k}" data-num="${k}" type="number" min="${min}" max="${max}" value="${c[k]}"></div>`;
  set(el, html`<div class="page-head"><div><h1>Settings</h1></div><button class="btn primary" id="save" data-busy="Saving...">Save settings</button></div>
    <div class="card"><h2>Notifications</h2>
      <p class="small">You get a notification when a job scores <b id="thrv">${c.alert_threshold}</b>% or higher, plus a daily nudge when follow-ups are due.</p>
      <input type="range" id="thr" min="50" max="100" step="1" value="${c.alert_threshold}" aria-label="Alert threshold">
      <div class="chips" style="margin:12px 0"><span class="badge ${ch.web_push_devices ? "good" : ""}">Push devices: ${ch.web_push_devices}</span>
        <span class="badge ${ch.ntfy ? "good" : ""}">ntfy: ${ch.ntfy ? "on" : "off"}</span><span class="badge ${ch.telegram ? "good" : ""}">Telegram: ${ch.telegram ? "on" : "off"}</span></div>
      <div class="row"><button class="btn primary" id="push" data-busy="Enabling...">${icon("bell")} Enable push on this device</button><button class="btn" id="test" data-busy="Sending...">Send a test notification</button></div>
      ${isIOS() && !standalone() ? html`<p class="notice small" style="margin-top:12px">iPhone: tap <b>Share</b> > <b>Add to Home Screen</b>, open jobkit from the Home Screen, then tap Enable push.</p>` : ""}
      <details style="margin-top:14px"><summary class="small"><b>Backup channels</b>: ntfy (works on every phone) and Telegram</summary>
        <div class="grid g2" style="margin-top:10px">
          <div class="field"><label for="ntfy">ntfy topic</label><div class="row" style="flex-wrap:nowrap"><input id="ntfy" type="text" value="${c.ntfy_topic}" placeholder="long random name"><button class="btn sm" id="gen" type="button">Generate</button></div>
            <div class="small muted">Install the free ntfy app, tap Subscribe and enter this exact topic. Anyone who knows the topic can read it, so keep it random.</div></div>
          <div class="field"><label for="tg">Telegram chat id</label><input id="tg" type="text" value="${c.telegram_chat_id}">
            <div class="small muted">Works if the admin set up a Telegram bot. Message the bot, then get your chat id from @userinfobot.</div></div></div></details>
    </div>
    <div class="card"><div class="spread"><h2>Job search</h2><button class="btn sm" id="rebuild" data-busy="Rebuilding...">Rebuild from my profile</button></div>
      <div class="grid g2">${list("search_terms", "Search terms", "what the job boards are searched for")}${list("title_keywords", "Title must contain one of")}</div>
      ${list("skills", "Skills to look for in descriptions")}
      <div class="grid g2">${list("open_locations", "Locations you can work from")}${list("closed_locations", "Location phrases that rule a job out")}</div>
      <div class="grid g2">${list("too_senior", "Seniority words that lower the score")}${list("bad_title", "Title words to skip")}</div>
      <div class="grid g3">${num("min_score", "Min keyword score to keep", 0, 100)}${num("max_age_days", "Max job age (days)", 1, 120)}${num("ai_prefilter_score", "Keyword score needed for AI scoring", 0, 100)}</div>
      <div class="grid g3">${num("ai_score_top_n", "Max AI-scored jobs per scan", 0, 100)}${num("heuristic_alert_score", "Alert score without AI", 0, 200)}</div>
    </div>
    <div class="card"><h2>Sources</h2><div class="grid g2">${s.sources.map((k) => html`<label class="switch"><input type="checkbox" data-src="${k}" ${c.sources[k] ? "checked" : ""}> ${SOURCE_INFO[k] || k}</label>`)}</div>
      <div class="grid g2" style="margin-top:14px">
        <div class="field"><label for="li">LinkedIn locations</label><input type="text" id="li" value="${c.linkedin.locations.join(", ")}"></div>
        <div class="field"><label for="jsl">JobSpy locations</label><input type="text" id="jsl" value="${c.jobspy.locations.join(", ")}"></div>
        <div class="field"><label for="adz">Adzuna countries <span class="muted">(gb, us, in, de...)</span></label><input type="text" id="adz" value="${c.adzuna_countries.join(", ")}"></div>
        <div class="field"><label for="jsq">JSearch queries</label><input type="text" id="jsq" value="${c.jsearch_queries.join(", ")}"></div></div></div>
    <div class="card"><h2>Company career pages</h2><p class="small muted">Add companies you'd love to work at, using the slug from their careers URL: boards.greenhouse.io/<b>slug</b>, jobs.lever.co/<b>slug</b>, jobs.ashbyhq.com/<b>slug</b>.</p>
      <div class="grid g3">${["greenhouse", "lever", "ashby"].map((a) => html`<div class="field"><label>${a}</label><textarea data-ats="${a}">${(c.ats_companies[a] || []).join("\n")}</textarea></div>`)}</div></div>
    ${s.env ? html`<div class="card"><h2>Server keys <span class="muted small">(admin)</span></h2><div class="chips">${Object.entries(s.env).map(([k, v]) => html`<span class="badge ${v ? "good" : ""}">${v ? "✓" : "✗"} ${k}</span>`)}</div>
      <p class="small muted" style="margin-top:8px">Set these in .env.local on the server and restart.</p></div>` : ""}`);
  $("#thr", el).oninput = (e) => ($("#thrv", el).textContent = e.target.value);
  $("#gen", el).onclick = () => { const a = new Uint8Array(12); crypto.getRandomValues(a); $("#ntfy", el).value = "jobkit-" + [...a].map((b) => b.toString(16).padStart(2, "0")).join(""); };
  $("#push", el).onclick = (e) => busy(e.currentTarget, async () => { const r = await enablePush(); toast(`Push on. ${r.devices} device(s) registered.`); route(); });
  $("#test", el).onclick = (e) => busy(e.currentTarget, async () => { const r = await api("POST", "/api/push/test"); toast("Sent: " + Object.entries(r).map(([k, v]) => `${k} ${v}`).join(", ")); });
  $("#rebuild", el).onclick = (e) => busy(e.currentTarget, async () => {
    const { profile } = await api("GET", "/api/profile");
    await api("PUT", "/api/profile", { profile, rebuild_search: true });
    toast("Search keywords rebuilt from your profile"); route();
  });
  $("#save", el).onclick = (e) => busy(e.currentTarget, async () => {
    const cfg = { alert_threshold: +$("#thr", el).value, ntfy_topic: $("#ntfy", el).value.trim(), telegram_chat_id: $("#tg", el).value.trim(),
      sources: Object.fromEntries($$("[data-src]", el).map((i) => [i.dataset.src, i.checked])),
      linkedin: { ...c.linkedin, locations: splitList($("#li", el).value) }, jobspy: { ...c.jobspy, locations: splitList($("#jsl", el).value) },
      adzuna_countries: splitList($("#adz", el).value), jsearch_queries: splitList($("#jsq", el).value),
      ats_companies: Object.fromEntries($$("[data-ats]", el).map((t) => [t.dataset.ats, splitList(t.value.toLowerCase())])) };
    $$("[data-list]", el).forEach((t) => (cfg[t.dataset.list] = splitList(t.value)));
    $$("[data-num]", el).forEach((i) => (cfg[i.dataset.num] = +i.value));
    await api("PUT", "/api/settings", { config: cfg });
    S.me = null; toast("Settings saved. They apply from the next scan.");
  });
}

// ---------- admin ----------
async function pageAdmin(el) {
  const a = await api("GET", "/api/admin");
  const joinLink = (code) => `${location.origin}/#/join/${code}`;
  const share = (code) => `Here's your invite to jobkit - it finds jobs that fit you and writes a tailored CV, cover letter and recruiter emails: ${joinLink(code)}\n\nYou'll need an authenticator app on your phone (Google Authenticator, Microsoft Authenticator, Authy or 1Password). The link works once and expires in 7 days.`;
  set(el, html`<div class="page-head"><div><h1>Admin</h1><div class="muted small">Only people you send an invite link can join. Each has their own profile, jobs and applications.
      ${a.ai_daily_limit > 0 ? ` Invited users get ${a.ai_daily_limit} AI actions a day (you're unlimited).` : ""}</div></div>
      <button class="btn primary" id="inv" data-busy="Creating...">Create invite link</button></div>
    <div id="newinv"></div>
    <div class="card"><h2>Users</h2><div class="table-wrap"><table><tr><th>User</th><th>Role</th><th>Profile</th><th>Recovery codes left</th><th>Joined</th><th></th></tr>
      ${a.users.map((u) => html`<tr><td><b>${u.uid}</b></td><td>${u.admin ? "admin" : "user"}</td><td>${u.has_profile ? "yes" : "no"}</td><td>${u.recovery_left}</td><td class="small">${(u.created || "").slice(0, 10)}</td>
        <td><div class="row"><button class="btn sm" data-reset="${u.uid}">Reset authenticator</button>${u.uid !== S.me.uid ? html`<button class="btn sm danger" data-del="${u.uid}">Remove</button>` : ""}</div></td></tr>`)}</table></div></div>
    <div class="card"><h2>Invite links</h2><p class="small muted">Each link works once and expires after 7 days. Revoke any you sent by mistake.</p>
      ${a.invites.length ? html`<div class="table-wrap"><table><tr><th>Link</th><th>For</th><th>Status</th><th>Created</th><th></th></tr>
      ${a.invites.slice().reverse().map((i) => html`<tr><td class="mono small">/#/join/${i.code}</td><td>${i.for_user ? `re-enrol ${i.for_user}` : "new user"}</td>
        <td><span class="badge ${i.status === "active" ? "good" : ""}">${i.status === "used" ? `used by ${i.used_by}` : i.status}</span></td>
        <td class="small">${(i.created || "").slice(0, 16)}</td>
        <td>${i.status === "active" ? html`<button class="btn sm danger" data-revoke="${i.code}">Revoke</button>` : ""}</td></tr>`)}</table></div>`
      : html`<p class="muted small">No invites yet.</p>`}</div>
    <div class="card"><h2>Server</h2><div class="chips">${Object.entries(a.env).map(([k, v]) => html`<span class="badge ${v ? "good" : ""}">${v ? "✓" : "✗"} ${k}</span>`)}</div>
      <p class="small muted" style="margin-top:8px">Last scan ${ago(a.meta.last_run)}: ${a.meta.fetched || 0} fetched, ${a.meta.unique || 0} unique.</p></div>`);
  const showLink = (title, code, text) => {
    set($("#newinv", el), html`<div class="card" style="border-color:var(--accent);margin-bottom:16px"><h2>${title}</h2>
      <p class="mono" style="font-size:1rem">${joinLink(code)}</p>
      <div class="row"><button class="btn primary" id="cpl">Copy link</button><button class="btn" id="cpc">Copy with message</button>
        ${navigator.share ? html`<button class="btn" id="shr">Share...</button>` : ""}</div></div>`);
    $("#cpl", el).onclick = () => copy(joinLink(code));
    $("#cpc", el).onclick = () => copy(text);
    const shr = $("#shr", el);
    if (shr) shr.onclick = () => navigator.share({ title: "jobkit invite", text, url: joinLink(code) }).catch(() => {});
  };
  $("#inv", el).onclick = (e) => busy(e.currentTarget, async () => { const { code } = await api("POST", "/api/admin/invite"); showLink("Invite link ready", code, share(code)); });
  $$("[data-reset]", el).forEach((b) => (b.onclick = () => {
    if (!confirm(`Log ${b.dataset.reset} out everywhere and create a link to set up a new authenticator? Their data is kept.`)) return;
    busy(b, async () => {
      const { code } = await api("POST", `/api/admin/users/${b.dataset.reset}/reset`);
      showLink(`Re-enrol link for ${b.dataset.reset}`, code, `Open this link to set up jobkit on your new phone: ${joinLink(code)}`);
    });
  }));
  $$("[data-revoke]", el).forEach((b) => (b.onclick = () => busy(b, async () => {
    await api("DELETE", `/api/admin/invites/${encodeURIComponent(b.dataset.revoke)}`); toast("Invite revoked"); route();
  })));
  $$("[data-del]", el).forEach((b) => (b.onclick = () => {
    if (!confirm(`Remove ${b.dataset.del}'s account? Their files stay on the server until you delete them.`)) return;
    busy(b, async () => { await api("DELETE", `/api/admin/users/${b.dataset.del}`); toast("Removed"); route(); });
  }));
}

async function pageMore(el) {
  set(el, html`<h1>More</h1><div class="card"><div class="list">
    ${[["#/outreach", "Recruiter outreach", "mail"], ["#/profile", "Profile and CV designs", "user"], ["#/settings", "Settings and notifications", "settings"],
       ...(S.me.admin ? [["#/admin", "Admin: users and invites", "shield"]] : [])].map(([h, l, i]) =>
      html`<a class="item" href="${h}" style="color:var(--text);align-items:center">${icon(i)}<span class="body title">${l}</span></a>`)}
    </div></div>
    <div class="row" style="margin-top:16px">${S.install ? html`<button class="btn" id="inst">Install jobkit as an app</button>` : ""}
    <button class="btn danger" id="lo">Log out ${S.me.uid}</button></div>`);
  $("#lo", el).onclick = async () => { await api("POST", "/api/auth/logout"); S.me = null; go("#/login"); };
  const inst = $("#inst", el);
  if (inst) inst.onclick = () => { S.install.prompt(); S.install = null; inst.remove(); };
}

// ---------- boot ----------
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); S.install = e; $("#installBtn")?.classList.remove("hidden"); });
window.addEventListener("hashchange", route);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
route();
