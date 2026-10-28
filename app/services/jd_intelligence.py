"""Job-description intelligence: turns the raw JD text into structured signals -- what the
employer actually asked for, whether the candidate's own profile has evidence for it, how
urgently this specific listing reads, and which hard constraints would block an application
outright. Everything here is extracted from the posting's own text; nothing is guessed about
the employer's internal hiring process.
"""
import re
from .scoring import required_years
from .job_intelligence import work_auth as _work_auth

MUST_CUES = [r'must have', r'required', r'requirement[s]?:', r'you have', r'you must',
    r'minimum qualifications', r'you (?:are|possess)', r'essential']
NICE_CUES = [r'nice to have', r'preferred', r'bonus', r'plus if', r'it.?s a plus',
    r'would be great', r'ideally', r'desirable']


def _split_sentences(text):
    # JD bullet points are usually one requirement per line; fall back to sentence-splitting
    # for prose-style descriptions.
    lines = [l.strip(" •-*\t") for l in text.splitlines() if l.strip()]
    out = []
    for l in lines:
        if len(l) > 220:
            out.extend(s.strip() for s in re.split(r'(?<=[.!?])\s+', l) if s.strip())
        else:
            out.append(l)
    return out


def extract_requirements(text):
    """JI01: must-have vs nice-to-have phrases, pulled from the JD's own cue language."""
    sentences = _split_sentences(text or "")
    must, nice, other = [], [], []
    must_re = re.compile("|".join(MUST_CUES), re.I)
    nice_re = re.compile("|".join(NICE_CUES), re.I)
    for s in sentences:
        if len(s) < 6 or len(s) > 300:
            continue
        if nice_re.search(s):
            nice.append(s)
        elif must_re.search(s):
            must.append(s)
    return {"must_have": must[:25], "nice_to_have": nice[:25]}


def requirement_gap_report(jd_text, profile):
    """JI02: red/amber/green evidence map -- does the candidate's own profile text contain
    something matching each extracted requirement phrase?"""
    reqs = extract_requirements(jd_text)
    skill_terms = [s.lower() for s in sum(profile.get("skills", {}).values(), [])]
    evidence_blob = " ".join(
        b for section in ("experience", "projects") for e in profile.get(section, []) for b in e.get("bullets", [])
    ).lower()
    rows = []
    for level, items in (("must_have", reqs["must_have"]), ("nice_to_have", reqs["nice_to_have"])):
        for r in items:
            rl = r.lower()
            hit_skills = [s for s in skill_terms if s and s in rl]
            hit_evidence = any(s for s in skill_terms if s and s in rl and s in evidence_blob)
            if hit_evidence:
                status = "green"
            elif hit_skills:
                status = "amber"
            else:
                status = "red"
            rows.append({"requirement": r, "level": level, "status": status,
                "matched_skills": hit_skills})
    return rows


_STATE_SIGNALS = [
    ("rolling", [r'rolling basis', r'applications? (?:are|is) reviewed on a rolling basis']),
    ("evergreen", [r'evergreen', r'always hiring', r'ongoing search']),
    ("urgent", [r'urgent(?:ly)?', r'immediate(?:ly)? need', r'asap']),
    ("multiple_hires", [r'multiple (?:hires|positions|openings)', r'several (?:roles|positions)']),
    ("confidential_replacement", [r'confidential (?:search|role)', r'replacement (?:hire|role)']),
    ("new_team", [r'new team', r'newly formed team', r'founding (?:member|team)']),
    ("pipeline", [r'general (?:application|pipeline)', r'talent pipeline', r'future opportunities']),
]


def application_state_signal(text):
    """JI06: language suggesting evergreen/rolling/urgent/pipeline hiring -- an inference from
    wording, never a claim about the employer's actual internal state."""
    t = (text or "").lower()
    matches = []
    for label, patterns in _STATE_SIGNALS:
        for p in patterns:
            if re.search(p, t):
                matches.append(label)
                break
    return {"signals": matches, "confidence": "inference_from_wording_only"}


_TRAVEL_RE = re.compile(r'(\d{1,3})\s*%\s*travel|travel\s*(?:up to|of)?\s*(\d{1,3})\s*%', re.I)
_SHIFT_RE = re.compile(r'\b(night shift|weekend (?:work|shifts?)|on-?call|rotating shift[s]?)\b', re.I)
_LANGUAGE_RE = re.compile(r'(fluent|native|professional proficiency)\s+(german|french|spanish|dutch|italian)', re.I)


def hard_constraint_preflight(job, profile):
    """JI12: consolidated deal-breaker check -- years of experience, work authorization,
    language, travel percentage, shift work -- so a blocked application is caught before time
    is spent tailoring it."""
    text = job.get("description", "") or ""
    location = job.get("location", "") or ""
    p = profile.get("preferences", {})
    constraints = []

    max_years = p.get("max_years_experience")
    req_years = required_years(text)
    if req_years is not None and max_years is not None:
        constraints.append({"constraint": "years_of_experience", "required": req_years,
            "candidate_max": max_years,
            "status": "blocked" if req_years > max_years + 1 else "ok"})

    wa = _work_auth(text, location)
    constraints.append({"constraint": "work_authorization", "signal": wa,
        "status": "blocked" if wa == "US_CITIZENSHIP_REQUIRED" else "ok" if wa in
            {"REMOTE_WORLDWIDE", "CONTRACTOR_SUPPORTED", "EOR_SUPPORTED"} else "review"})

    lang = _LANGUAGE_RE.search(text)
    if lang:
        known = {k.lower() for k in profile.get("candidate", {}).get("languages", {}).keys()}
        have_it = lang.group(2).lower() in known
        constraints.append({"constraint": "language_requirement",
            "required": f"{lang.group(1)} {lang.group(2)}",
            "status": "ok" if have_it else "review"})

    travel = _TRAVEL_RE.search(text)
    if travel:
        pct = int(travel.group(1) or travel.group(2))
        constraints.append({"constraint": "travel_percentage", "required_pct": pct,
            "status": "review" if pct > 10 else "ok"})

    shift = _SHIFT_RE.search(text)
    if shift:
        constraints.append({"constraint": "shift_work", "signal": shift.group(1),
            "status": "review"})

    blocked = [c for c in constraints if c["status"] == "blocked"]
    return {"constraints": constraints, "any_blocked": bool(blocked)}
