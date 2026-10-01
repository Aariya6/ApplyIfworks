"""Project priority scoring: "which project should be built first to maximize useful portfolio
evidence" — not an employment-probability guess. Every input is real, already-computed evidence
already in this database (matching job counts, skill-gap overlap, role-family breadth). Reasons
are always shown alongside the score so the number can be inspected, not just trusted.
"""
from .portfolio_evidence import compute_project_job_evidence

# Feasibility and differentiation are the two genuinely subjective inputs here — hand-set per
# project based on the real research already done (license findings, stack complexity), not
# fabricated. Documented plainly rather than hidden inside a black-box formula.
FEASIBILITY_NOTES={
    "career-intelligence": (9, "Fresh build, no license risk, stack is standard (FastAPI+Postgres+pgvector); smallest scope of the five"),
    "music-composition-lab": (6, "Fresh build on Tone.js (MIT); custom piano-roll UI is real engineering effort"),
    "forensic-case-board": (5, "Fresh build; NLP entity extraction + graph reasoning is more open-ended engineering"),
    "agora-agent-simulation": (5, "Fresh build; simulation performance/determinism work is non-trivial"),
    "literary-atlas": (4, "Largest scope of the five: ingestion pipeline + ES + pgvector + citation-validated LLM extraction"),
}

def score_project(project, skill_gap_signals):
    evidence=compute_project_job_evidence(project)
    gap_skills={s["skill"] for s in skill_gap_signals}
    declared_skills=set(evidence["declared_skills"])
    gaps_addressed=declared_skills & gap_skills

    reasons=[]
    score=0.0

    jobs_component=min(30, evidence["matching_job_count"]*0.3)
    score+=jobs_component
    reasons.append(f"{evidence['matching_job_count']} matching jobs in current database (+{jobs_component:.1f})")

    gaps_component=len(gaps_addressed)*8
    score+=gaps_component
    reasons.append(f"addresses {len(gaps_addressed)} of the top recurring skill gaps ({', '.join(sorted(gaps_addressed)) or 'none'}) (+{gaps_component})")

    breadth_component=len(evidence["role_families_strengthened"])*4
    score+=breadth_component
    reasons.append(f"strengthens {len(evidence['role_families_strengthened'])} role families (+{breadth_component})")

    feas,feas_note=FEASIBILITY_NOTES.get(project["id"],(5,"not assessed"))
    feas_component=feas*2
    score+=feas_component
    reasons.append(f"feasibility {feas}/10 — {feas_note} (+{feas_component})")

    return round(score,1), reasons, evidence

def rank_projects():
    from ..db import portfolio_projects, skill_gap_signals as db_signals
    import json
    signals=[{**s,"example_job_ids":json.loads(s["example_job_ids"])} for s in db_signals()]
    ranked=[]
    for p in portfolio_projects():
        score,reasons,evidence=score_project(p,signals)
        ranked.append({"project":p,"score":score,"reasons":reasons,"evidence":evidence})
    ranked.sort(key=lambda r:-r["score"])
    return ranked
