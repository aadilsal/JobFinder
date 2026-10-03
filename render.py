"""Render tailored CV and cover letter to ATS-friendly single-column PDFs in a choice of designs."""
from datetime import date
from xml.sax.saxutils import escape as esc
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, HRFlowable

# Every design is single column with real text (no tables, images or columns) so ATS parsers read it cleanly.
THEMES = {
    "classic":   dict(label="Classic - black and white, safest for ATS", accent="#111111", regular="Helvetica",
                      bold="Helvetica-Bold", size=9.0, name=18, margin=14, caps=True),
    "modern":    dict(label="Modern - blue accent headings", accent="#1D4ED8", regular="Helvetica",
                      bold="Helvetica-Bold", size=9.0, name=20, margin=14, caps=False),
    "executive": dict(label="Executive - serif, traditional", accent="#1F2937", regular="Times-Roman",
                      bold="Times-Bold", size=10.0, name=19, margin=16, caps=True),
    "compact":   dict(label="Compact - fits more on one page", accent="#0F766E", regular="Helvetica",
                      bold="Helvetica-Bold", size=8.5, name=16, margin=11, caps=True),
}
GREY_HEX = "#555555"
GREY = colors.HexColor(GREY_HEX)
DARK = colors.HexColor("#111111")


def _styles(theme):
    t = THEMES.get(theme, THEMES["classic"])
    acc, r, b, z = colors.HexColor(t["accent"]), t["regular"], t["bold"], t["size"]
    return t, {
        "name": ParagraphStyle("name", fontName=b, fontSize=t["name"], leading=t["name"] * 1.18,
                               textColor=acc if theme == "modern" else DARK),
        "head": ParagraphStyle("head", fontName=r, fontSize=z + 1, leading=z * 1.45, textColor=GREY),
        "contact": ParagraphStyle("contact", fontName=r, fontSize=z - 0.5, leading=z * 1.25, textColor=GREY),
        "sec": ParagraphStyle("sec", fontName=b, fontSize=z + 0.5, leading=z * 1.35, textColor=acc,
                              spaceBefore=z * 0.75, spaceAfter=1),
        "body": ParagraphStyle("body", fontName=r, fontSize=z, leading=z * 1.31, textColor=DARK),
        "role": ParagraphStyle("role", fontName=b, fontSize=z + 0.3, leading=z * 1.33, textColor=DARK, spaceBefore=3),
        "bul": ParagraphStyle("bul", fontName=r, fontSize=z, leading=z * 1.29, leftIndent=10, bulletIndent=1,
                              textColor=DARK),
        "letter": ParagraphStyle("letter", fontName=r, fontSize=10.5, leading=15, textColor=DARK, spaceAfter=9),
    }


def _link(v, color=GREY_HEX):
    href = f"mailto:{v}" if "@" in v and not v.startswith("http") else (v if v.startswith("http") else f"https://{v}")
    return f'<link href="{esc(href)}" color="{color}">{esc(v)}</link>'


def _header(st, profile, S, headline=""):
    st.append(Paragraph(esc(profile["name"]), S["name"]))
    if headline:
        st.append(Paragraph(esc(headline), S["head"]))
    parts = [esc(profile["location"]), _link(profile["email"]), esc(profile["phone"])] + \
            [_link(v) for v in profile.get("links", {}).values()]
    st.append(Paragraph("  |  ".join(parts), S["contact"]))


def _section(st, title, S, t):
    st.append(Paragraph(esc(title.upper() if t["caps"] else title), S["sec"]))
    st.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor(t["accent"]), spaceAfter=3))


def _bullets(st, items, S):
    for b in items:
        st.append(Paragraph(esc(b), S["bul"], bulletText="•"))


def render_cv(profile, c, path, theme="classic"):
    t, S = _styles(theme)
    m = t["margin"] * mm
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=m, rightMargin=m, topMargin=m * 0.8, bottomMargin=m * 0.7,
                            title=f"{profile['name']} - CV", author=profile["name"])
    grey = f'<font color="{GREY_HEX}" name="{t["regular"]}">'
    st = []
    _header(st, profile, S, c.get("headline", ""))

    _section(st, "Professional Summary", S, t)
    st.append(Paragraph(esc(c["summary"]), S["body"]))

    _section(st, "Technical Skills", S, t)
    for row in c["skills"]:
        st.append(Paragraph(f"<b>{esc(row['label'])}:</b> {esc(', '.join(row['items']))}", S["body"]))

    _section(st, "Professional Experience", S, t)
    by_id = {e["id"]: e for e in profile["experience"]}
    for ex in c["experience"]:
        base = by_id.get(ex["id"])
        if not base:
            continue
        st.append(Paragraph(f"{esc(base['title'])} | {esc(base['company'])}, {esc(base['location'])} "
                            f"{grey}| {esc(base['dates'])}</font>", S["role"]))
        _bullets(st, ex["bullets"], S)

    if c.get("projects"):
        _section(st, "Projects", S, t)
        for p in c["projects"]:
            tech = f" {grey}| {esc(p['tech'])}</font>" if p.get("tech") else ""
            url = f" | {_link(p['url'].replace('https://', ''), t['accent'])}" if p.get("url") else ""
            st.append(Paragraph(f"{esc(p['name'])}{tech}{url}", S["role"]))
            _bullets(st, p["bullets"], S)

    _section(st, "Education and Certifications", S, t)
    for e in profile["education"]:
        st.append(Paragraph(f"<b>{esc(e['degree'])}</b> | {esc(e['school'])} | {esc(e['dates'])}", S["body"]))
    if profile.get("certifications"):
        st.append(Paragraph(esc(" | ".join(profile["certifications"])), S["body"]))
    doc.build(st)


def render_letter(profile, c, path, theme="classic"):
    t, S = _styles(theme)
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=22*mm, rightMargin=22*mm,
                            topMargin=20*mm, bottomMargin=18*mm, title=f"{profile['name']} - Cover Letter",
                            author=profile["name"])
    st = []
    _header(st, profile, S)
    st += [HRFlowable(width="100%", thickness=0.6, color=colors.HexColor(t["accent"]), spaceBefore=4, spaceAfter=10),
           Paragraph(date.today().strftime("%d %B %Y"), S["letter"])]
    paras = [p.strip() for p in c["cover_letter"].split("\n\n") if p.strip()]
    if paras and not paras[0].lower().startswith(("dear", "hi", "hello", "to ")):
        paras.insert(0, "Dear Hiring Team,")
    if paras and profile["name"].split()[0] not in paras[-1]:
        paras.append(f"Sincerely,\n{profile['name']}")
    for para in paras:
        st.append(Paragraph(esc(para).replace("\n", "<br/>"), S["letter"]))
    doc.build(st)
