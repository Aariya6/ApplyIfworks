"""Project -> job evidence: for a given portfolio project's declared skills_demonstrated, find
which real jobs in the database (QUALIFIED/TRANSFERABLE/STRETCH only — a project doesn't
'strengthen fit' for a job that was never a credible fit) actually ask for those skills, and which
companies those jobs belong to. Every number here comes from the existing job database; nothing is
estimated or invented.
"""
import re
from .skill_gap import _SKILL_PATTERNS, SKILL_TAXONOMY

def _parse_list(csv_field):
    return [s.strip().lower() for s in (csv_field or "").split(",") if s.strip()]

def compute_project_job_evidence(project):
    """skills_demonstrated is a comma-separated field on the project row. Falls back to
    required_skills if skills_demonstrated hasn't been filled in yet (pre-build specs)."""
    from ..db import jobs
    declared=_parse_list(project.get("skills_demonstrated")) or _parse_list(project.get("required_skills"))
    # Only match against skills we actually have a real taxonomy pattern for — free-text fields
    # like "React" or "FastAPI" that aren't in SKILL_TAXONOMY are reported as declared-but-unmatched
    # rather than silently ignored, so the gap in matching is visible, not hidden.
    matched_patterns={s:_SKILL_PATTERNS[s] for s in declared if s in _SKILL_PATTERNS}
    unmatched_declared=[s for s in declared if s not in _SKILL_PATTERNS]

    js=[j for j in jobs(10000) if (j.get("fit_tier") or "MISMATCH") in {"QUALIFIED","TRANSFERABLE","STRETCH"}]
    matched_jobs=[]
    for j in js:
        text=(j.get("title","")+" "+(j.get("description","") or "")).lower()
        hits=[s for s,pat in matched_patterns.items() if pat.search(text)]
        if hits: matched_jobs.append((j,hits))

    companies=sorted({j.get("company") for j,_ in matched_jobs if j.get("company")})
    role_families=sorted({j.get("role_family") for j,_ in matched_jobs if j.get("role_family")})
    skill_hit_counts={s:sum(1 for _,hits in matched_jobs if s in hits) for s in matched_patterns}

    return {
        "declared_skills": declared,
        "unmatched_declared_skills": unmatched_declared,
        "matching_job_count": len(matched_jobs),
        "matching_job_ids": [j["id"] for j,_ in matched_jobs][:30],
        "companies_strengthened": companies[:30],
        "role_families_strengthened": role_families,
        "skill_hit_counts": skill_hit_counts,
    }
