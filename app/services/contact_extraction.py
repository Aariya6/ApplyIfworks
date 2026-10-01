"""Cold-outreach support, built only from data this project already legitimately has: text
already scraped into the jobs/companies tables (job descriptions, raw ATS payloads, company
notes). This deliberately does NOT scrape LinkedIn or query third-party contact/email-finder
databases -- those carry real ToS, account-ban and data-provenance risk that a regex over your own
already-collected text doesn't. If a posting or company record never mentioned a human contact,
this correctly finds nothing rather than guessing one.
"""
import re, json

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Requires at least one separator character (space, dash, parens) or a leading + -- a bare run of
# digits with no phone-like formatting is far more likely to be a numeric id pulled out of a raw
# JSON payload (confirmed: this is exactly what an unformatted-digit-run regex actually matched
# against real scraped data) than an actual phone number.
PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d]{0,3}[\-\s()][\d\-\s()]{5,}\d)(?!\d)")

# Local-parts that are almost always automated/tracking addresses, not a person worth a cold
# email -- surfacing these would waste the person's time on a dead end.
_NOISE_LOCALPARTS = {
    "noreply", "no-reply", "donotreply", "do-not-reply", "support", "privacy", "legal",
    "abuse", "unsubscribe", "webmaster", "postmaster", "info", "notifications",
}


def extract_emails(text):
    seen = []
    for m in EMAIL_RE.finditer(text or ""):
        email = m.group(0)
        local = email.split("@")[0].lower()
        if local in _NOISE_LOCALPARTS:
            continue
        if email.lower() not in (e.lower() for e in seen):
            seen.append(email)
    return seen


def extract_phones(text):
    seen = []
    for m in PHONE_RE.finditer(text or ""):
        raw = m.group(0).strip()
        digits = re.sub(r"\D", "", raw)
        if not (8 <= len(digits) <= 15):
            continue
        if raw not in seen:
            seen.append(raw)
    return seen


def _raw_json_text(job):
    try:
        return json.dumps(json.loads(job.get("raw_json") or "{}"), ensure_ascii=False)
    except Exception:
        return job.get("raw_json") or ""


def contacts_for_job(job):
    text = " ".join([job.get("description") or "", _raw_json_text(job)])
    return {"emails": extract_emails(text), "phones": extract_phones(text)}


def contacts_for_company(company):
    text = " ".join(str(company.get(k) or "") for k in ("notes", "careers_url", "website"))
    return {"emails": extract_emails(text), "phones": extract_phones(text)}


def generate_cold_email_draft(profile, job):
    """Deterministic only (no LLM call) -- reuses the same relevance-ranking and plain,
    literate voice as paste_sheet.py's fallback so tone stays consistent across every generated
    document in this project."""
    from .paste_sheet import _most_relevant
    c = profile["candidate"]
    title = job.get("title") or "this role"
    company = job.get("company") or "your team"
    job_text = title + " " + (job.get("description") or "")
    exp = profile.get("experience", [])
    top_exp = _most_relevant(exp, lambda e: e.get("title", "") + " " + " ".join(e.get("bullets", [])), job_text)
    exp_line = f"At {top_exp.get('company', '')}, {top_exp.get('bullets', [''])[0].rstrip('.')}." if top_exp else ""
    subject = f"{c.get('name', '')} — {title} at {company}"
    body = (
        f"Hi,\n\n"
        f"I'm reaching out directly about the {title} role at {company} -- I didn't want this to "
        f"just be another form submission with no one reading it. {exp_line}\n\n"
        f"I think the fit is close enough to be worth a few minutes of your time. If there's a "
        f"better process or a more relevant person for this, I'd genuinely appreciate a pointer -- "
        f"resume attached either way.\n\n"
        f"{c.get('name', '')}\n{c.get('email', '')}"
        + (f" · {c.get('phone')}" if c.get("phone") else "")
        + (f"\n{c.get('linkedin')}" if c.get("linkedin") else "")
    )
    return {"subject": subject, "body": body}
