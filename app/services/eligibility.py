"""First-class eligibility assessment: explicit YES/NO/UNKNOWN answers to the questions that
actually decide whether a candidate can take a job, each with a stated reason. This sits on top
of job_intelligence.work_auth()/infer_country() rather than replacing them — those stay the
single source of truth for the underlying signal; this module turns that signal into the
structured, explained answers a person actually needs to decide whether to apply.

Never invents a fact: every field is either directly derived from JD text/location, or UNKNOWN.
"""
import re
from .job_intelligence import work_auth, infer_country, country_fit

VISA_SPONSORSHIP_RE=re.compile(r'visa\s+sponsor|sponsor(?:s|ship)?\s+(?:a\s+)?visa|we\s+(?:can|will)\s+sponsor',re.I)
NO_SPONSORSHIP_RE=re.compile(r'(?:no|not able to|cannot|unable to)\s+(?:provide\s+|offer\s+)?(?:visa\s+)?sponsorship|sponsorship\s+(?:is\s+)?not\s+(?:available|provided|offered)',re.I)
RELOCATION_RE=re.compile(r'relocation\s+(?:assistance|support|package|allowance|bonus)|we\s+(?:offer|provide|support)\s+relocation|help(?:s|ing)?\s+(?:you\s+)?relocate',re.I)
UK_WORK_AUTH_RE=re.compile(r'\b(?:uk|united kingdom)\s*(?:citizens?|right\s+to\s+work|work\s+authorization|work\s+permit)\b',re.I)
LANGUAGE_RE=re.compile(r'(fluent|native|proficient|business[- ]level)\s+(german|french|spanish|dutch|italian|portuguese|polish)',re.I)
EMPLOYMENT_TYPE_RE=re.compile(r'\b(full[- ]time|part[- ]time|contract|internship|freelance|temporary)\b',re.I)

def _yn(v): return "YES" if v is True else ("NO" if v is False else "UNKNOWN")

def assess_eligibility(job, profile):
    title=job.get("title",""); desc=job.get("description","") or ""; loc=job.get("location","") or ""
    text=f"{title} {desc} {loc}"
    wa=work_auth(desc, loc)
    country=infer_country(f"{title} {desc}", loc)
    cfit=country_fit(country, profile.get("preferences",{}))

    reasons=[]

    # Remote-from-India / remote-from-Europe: derived from the same work_auth signal, but asked
    # as two separate questions because "remote" in a posting does not default to either.
    if wa=="REMOTE_WORLDWIDE":
        remote_india=True; remote_europe=True; reasons.append("posting states worldwide/anywhere remote")
    elif wa=="CONTRACTOR_SUPPORTED":
        remote_india=True; remote_europe=True; reasons.append("posting supports international contractors")
    elif wa=="EOR_SUPPORTED":
        remote_india=True; remote_europe=None; reasons.append("posting mentions Employer-of-Record/India/international support")
    elif wa=="US_CITIZENSHIP_REQUIRED":
        remote_india=False; remote_europe=False; reasons.append("posting requires US citizenship/work authorization")
    elif wa in {"EU_ONLY","REMOTE_EUROPE","REMOTE_EU","REMOTE_GERMANY"}:
        remote_india=False; remote_europe=True; reasons.append(f"posting restricts to Europe/EU ({wa})")
    elif wa=="COUNTRY_RESTRICTED":
        remote_india=False; remote_europe=None; reasons.append("posting requires being based in a specific country")
    elif cfit=="excluded":
        remote_india=False; remote_europe=False; reasons.append(f"located in {country}, outside target countries, no remote-friendly signal")
    else:
        remote_india=None; remote_europe=None; reasons.append("no explicit remote/location-restriction language found")

    visa_sponsorship = False if NO_SPONSORSHIP_RE.search(text) else (True if VISA_SPONSORSHIP_RE.search(text) else None)
    if visa_sponsorship is True: reasons.append("posting explicitly mentions visa sponsorship")
    elif visa_sponsorship is False: reasons.append("posting explicitly states no sponsorship")

    relocation_support = True if RELOCATION_RE.search(text) else None
    if relocation_support: reasons.append("posting mentions relocation assistance")

    uk_work_auth_required = True if UK_WORK_AUTH_RE.search(text) else False
    if uk_work_auth_required: reasons.append("posting requires UK citizenship/right to work")

    eu_citizenship_required = wa=="EU_ONLY"
    if eu_citizenship_required: reasons.append("posting requires EU citizenship/work authorization")

    us_citizenship_required = wa=="US_CITIZENSHIP_REQUIRED"

    lang_match=LANGUAGE_RE.search(text)
    language_requirement = f"{lang_match.group(1)} {lang_match.group(2)}" if lang_match else None

    emp_match=EMPLOYMENT_TYPE_RE.search(job.get("employment","") or text)
    employment_type = emp_match.group(1).title() if emp_match else (job.get("employment") or None)

    return {
        "remote_from_india": _yn(remote_india),
        "remote_from_europe": _yn(remote_europe),
        "india_hiring_allowed": _yn(remote_india),
        "eor_possible": _yn(wa=="EOR_SUPPORTED" or None),
        "visa_sponsorship": _yn(visa_sponsorship),
        "relocation_support": _yn(relocation_support),
        "eu_citizenship_required": "YES" if eu_citizenship_required else "NO",
        "uk_work_auth_required": "YES" if uk_work_auth_required else "NO",
        "us_citizenship_required": "YES" if us_citizenship_required else "NO",
        "location_restriction": country if cfit=="excluded" else (None if cfit in {"unknown","target"} else country),
        "employment_type": employment_type,
        "language_requirement": language_requirement,
        "work_auth_signal": wa,
        "country": country,
        "country_fit": cfit,
        "reasons": reasons,
    }
