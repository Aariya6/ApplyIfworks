"""Multi-dimensional application priority: deliberately NOT a single "hire probability" score.
Each dimension is a separate, explained, evidence-based signal so the person can see *why* a job
ranks where it does and disagree with any one part of it without the whole score being a black box.
"""
import json

_ATS_TIER={
    "greenhouse":1,"lever":1,"ashby":1,"workable":1,"smartrecruiters":1,  # official ATS, direct
    "personio":1,"teamtailor":1,"recruitee":1,
    "workday":2,"icims":2,"successfactors":2,"taleo":2,  # official but high-friction ATS
}

def source_quality(job):
    """1 = official company ATS (direct application), 2 = official but high-friction ATS,
    3 = reputable third-party board, 4 = aggregator/repost. Never claims a hiring-outcome
    difference between tiers -- just states what the source actually is."""
    ats=(job.get("ats") or "").lower()
    source=(job.get("source") or "").lower()
    if ats in _ATS_TIER: return _ATS_TIER[ats], f"official {ats} ATS"
    if source in {"greenhouse","lever","ashby","workable","smartrecruiters","company_universe","company_seed"}:
        return 1, "official company career page/registry"
    if source in {"remotive","arc","wellfound","nodesk","builtin","jobgether"}:
        return 3, f"reputable third-party board ({source})"
    return 4, f"aggregator/repost ({source or 'unknown source'})"


def compensation_fit(job, career_requirements):
    """Returns UNKNOWN unless the job actually states a number -- never guesses."""
    salary_data=job.get("salary_data")
    if isinstance(salary_data, str):
        try: salary_data=json.loads(salary_data)
        except Exception: salary_data=None
    if not salary_data or not salary_data.get("minimum"):
        return "UNKNOWN", "no salary information in the posting"
    minimum=salary_data.get("minimum")
    comp=career_requirements.get("compensation", {})
    floor=comp.get("minimum_acceptable_eur")
    if floor is None:
        return "UNKNOWN", "no minimum-acceptable compensation set in career_requirements"
    # extremely rough EUR-only comparison; currency conversion is explicitly not attempted
    if (salary_data.get("currency") or "EUR") != "EUR":
        return "UNKNOWN", f"posting is in {salary_data.get('currency')}, not compared against a EUR floor"
    if minimum >= floor: return "MEETS_MINIMUM", f"posting states {minimum}+ vs. floor {floor}"
    return "BELOW_MINIMUM", f"posting states {minimum} vs. floor {floor}"


def career_direction_fit(job, career_requirements):
    family=job.get("role_family","")
    rp=career_requirements.get("role_preferences", {})
    if family in rp.get("core", []): return "CORE", f"{family} is a core role preference"
    if family in rp.get("adjacent", []): return "ADJACENT", f"{family} is an adjacent role preference"
    if family in rp.get("exploratory", []): return "EXPLORATORY", f"{family} is the exploratory track"
    return "UNCLASSIFIED", f"{family} is not in any configured preference bucket"


def personalization_opportunity(job):
    """How much a deep personalization pass would actually add, given what's already known about
    this job -- not a quality judgment on the company. A job with more real, distinctive JD
    content to react to has more opportunity than a bare-bones one-line posting."""
    desc_len=len(job.get("description") or "")
    if desc_len > 2000: return "HIGH", f"JD is detailed ({desc_len} chars) — worth a targeted/deep pass"
    if desc_len > 500: return "MEDIUM", f"JD has moderate detail ({desc_len} chars)"
    return "LOW", f"JD is sparse ({desc_len} chars) — a fast/standard pass is proportionate"


def compute_priority_dimensions(job, profile):
    career_requirements=profile.get("career_requirements", {})
    sq_tier, sq_reason=source_quality(job)
    comp_fit, comp_reason=compensation_fit(job, career_requirements)
    direction, direction_reason=career_direction_fit(job, career_requirements)
    pers_opp, pers_reason=personalization_opportunity(job)
    return {
        "eligibility": job.get("eligibility","human_review"),
        "role_fit_tier": job.get("fit_tier","MISMATCH"),
        "role_fit_score": job.get("fit_score",0),
        "source_quality_tier": sq_tier,
        "source_quality_reason": sq_reason,
        "compensation_fit": comp_fit,
        "compensation_reason": comp_reason,
        "career_direction_fit": direction,
        "career_direction_reason": direction_reason,
        "personalization_opportunity": pers_opp,
        "personalization_reason": pers_reason,
    }
