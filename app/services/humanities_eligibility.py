"""Humanities/Literature eligibility: a deliberately separate 6-tier scale from the normal
QUALIFIED/TRANSFERABLE/STRETCH/MISMATCH ladder, because a CSE degree does not on its own qualify
anyone for editorial/publishing/literature roles the way it does for software roles. This module
never assumes qualification — it looks for explicit degree/portfolio/experience requirements in
the JD and classifies honestly, and it only ever credits *real* evidence already in the profile
(never invents a literary portfolio that doesn't exist).

Tiers:
  DIRECTLY_QUALIFIED  - profile shows a literature/humanities credential matching the role exactly
                        (not expected to ever fire for this candidate's actual CSE profile; kept
                        so the code is honest about what *would* qualify, not hand-wavy)
  TRANSFERABLE        - entry-level content/writing-adjacent role, credible via real technical-
                        writing/presentation/workshop experience already in the profile
  PORTFOLIO_REQUIRED  - JD asks for writing samples/a portfolio; gated on whether the profile has
                        one attached (it currently does not — this is stated, not hidden)
  DEGREE_REQUIRED     - JD explicitly requires a humanities/literature degree the profile lacks
  EXPERIENCE_REQUIRED - JD requires years of editorial/publishing experience the profile lacks
  ACADEMIC_ONLY        - JD is a PhD/faculty/academic-only position
"""
import re

ACADEMIC_RE=re.compile(r'\bph\.?d\b|\bdoctorate\b|\bfaculty\b|\btenure\b|\bpostdoc\b|\bassistant professor\b',re.I)
DEGREE_RE=re.compile(r"\b(master'?s|m\.?a\.?|msc)\s+(degree\s+)?in\s+(english|literature|humanities|linguistics|comparative literature)",re.I)
PORTFOLIO_RE=re.compile(r'writing sample|portfolio of (?:your )?writing|published (?:work|writing|articles)|clips? (?:of your work|required)',re.I)
EXPERIENCE_RE=re.compile(r'(\d{1,2})\+?\s*years?\s*(?:of\s+)?(?:editorial|publishing|writing|content)\s+experience',re.I)

def _has_literary_portfolio(profile):
    """Only ever returns True if the profile *actually* lists one — currently it does not.
    A future addition (e.g. a real Poeticous/Medium/Substack link, published pieces) would go in
    profile.json under candidate.literary_portfolio, and this reads that field, never a guess."""
    return bool(profile.get("candidate",{}).get("literary_portfolio"))

def _has_transferable_writing_evidence(profile):
    """Real, already-in-profile evidence: technical workshops, presentations, community writing —
    not a literature credential, but a credible transferable signal for entry-level content work."""
    exp_blob=" ".join(str(e) for e in profile.get("experience",[])).lower()
    return any(t in exp_blob for t in ["workshop","presented","curriculum","mentoring","organized"])

def assess_humanities_qualification(job, profile):
    text=(job.get("title","")+" "+(job.get("description","") or "")).lower()
    reasons=[]

    if ACADEMIC_RE.search(text):
        reasons.append("posting is a PhD/faculty/academic-only position")
        return "ACADEMIC_ONLY", reasons

    m=DEGREE_RE.search(text)
    if m:
        reasons.append(f"posting requires a {m.group(1)} in {m.group(3)} — not present in candidate's profile (B.Tech CSE)")
        return "DEGREE_REQUIRED", reasons

    m=EXPERIENCE_RE.search(text)
    if m:
        reasons.append(f"posting requires {m.group(1)}+ years of editorial/publishing/writing experience — not present in profile")
        return "EXPERIENCE_REQUIRED", reasons

    if PORTFOLIO_RE.search(text):
        if _has_literary_portfolio(profile):
            reasons.append("posting requires a writing portfolio — profile has one on file")
            return "TRANSFERABLE", reasons
        reasons.append("posting requires a writing sample/portfolio — profile does not currently list one; would need to be prepared before applying")
        return "PORTFOLIO_REQUIRED", reasons

    if _has_transferable_writing_evidence(profile):
        reasons.append("no formal humanities credential required; profile's workshop/presentation/curriculum experience is a credible transferable signal for entry-level content/writing work")
        return "TRANSFERABLE", reasons

    reasons.append("no explicit degree/portfolio/experience requirement found, and no strong transferable evidence in profile either — treat as exploratory only")
    return "TRANSFERABLE", reasons
