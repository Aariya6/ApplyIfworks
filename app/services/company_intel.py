"""Company intelligence: turns the company registry + its discovered jobs into a concrete,
explained fit assessment per company. No probability-of-getting-hired guessing — every field is
YES/NO/UNKNOWN/HIGH/MEDIUM/LOW/NONE derived from real discovered data, with stated reasons.
"""
import json

AI_SECTOR_TERMS=["ai","machine learning","artificial intelligence","ml ","llm","nlp","neural"]
ENGINEERING_FAMILIES={"AI_ENGINEERING","MLOPS_PLATFORM","DATA","SOFTWARE"}
PRODUCT_FAMILIES={"AI_PRODUCT","PRODUCT_MANAGEMENT","PROGRAM_MANAGEMENT"}
COMMS_FAMILIES={"DEVELOPER_RELATIONS","TECHNICAL_COMMUNICATION","COMMUNITY_OPERATIONS","AI_HUMANITIES","CONSULTING_SOLUTIONS"}

def _agg_eligibility(field, jobs_with_elig):
    """YES if any relevant job explicitly says YES, NO only if every relevant job explicitly
    says NO, UNKNOWN otherwise. Never invents a company-wide policy from zero evidence."""
    vals=set()
    for j in jobs_with_elig:
        try: d=json.loads(j.get("eligibility_detail") or "null")
        except Exception: d=None
        if d and d.get(field) in {"YES","NO"}: vals.add(d[field])
    if "YES" in vals: return "YES"
    if vals=={"NO"}: return "NO"
    return "UNKNOWN"

def assess_company_fit(company, company_jobs, profile):
    relevant=[j for j in company_jobs if (j.get("fit_tier") or "MISMATCH") in {"QUALIFIED","TRANSFERABLE","STRETCH"}]
    qualified=[j for j in relevant if j.get("fit_tier")=="QUALIFIED"]
    transferable=[j for j in relevant if j.get("fit_tier")=="TRANSFERABLE"]
    stretch=[j for j in relevant if j.get("fit_tier")=="STRETCH"]

    families={j.get("role_family") for j in relevant}
    engineering_relevance="HIGH" if any(f in ENGINEERING_FAMILIES for f in families) and qualified else ("MEDIUM" if any(f in ENGINEERING_FAMILIES for f in families) else "LOW")
    product_pm_relevance="HIGH" if any(f in PRODUCT_FAMILIES for f in families) else "NONE"
    comms_leadership_relevance="HIGH" if any(f in COMMS_FAMILIES for f in families) else "NONE"

    blob=((company.get("sector") or "")+" "+" ".join(j.get("title","")+" "+j.get("description","")[:300] for j in relevant)).lower()
    ai_relevance="HIGH" if sum(t in blob for t in AI_SECTOR_TERMS)>=2 else ("MEDIUM" if any(t in blob for t in AI_SECTOR_TERMS) else "LOW")

    remote_india=_agg_eligibility("remote_from_india",relevant)
    remote_europe=_agg_eligibility("remote_from_europe",relevant)
    eor=_agg_eligibility("eor_possible",relevant)
    visa=_agg_eligibility("visa_sponsorship",relevant)
    relocation=_agg_eligibility("relocation_support",relevant)

    why=[]
    if relevant: why.append(f"{len(relevant)} matching open role(s): {len(qualified)} qualified, {len(transferable)} transferable, {len(stretch)} stretch")
    else: why.append("no currently-open role in the registry matches this profile")
    if remote_india=="YES": why.append("at least one open role explicitly supports remote work from India")
    if company.get("ats") in {"greenhouse","lever","ashby","workable","smartrecruiters"}: why.append(f"low-friction application via {company.get('ats')} (official ATS, not an aggregator)")
    if ai_relevance=="HIGH": why.append("AI/ML is a central theme across this company's open roles")

    # A company earns a target tier only from concrete signal, never a guessed hire probability.
    if qualified and remote_india in {"YES","UNKNOWN"}: target_tier="PRIMARY_TARGET"
    elif relevant: target_tier="SECONDARY_TARGET"
    else: target_tier="NOT_CURRENTLY_ACTIONABLE"

    return {
        "target_tier": target_tier,
        "ai_product_relevance": ai_relevance,
        "engineering_relevance": engineering_relevance,
        "product_pm_relevance": product_pm_relevance,
        "comms_leadership_relevance": comms_leadership_relevance,
        "relevant_open_roles": len(relevant),
        "qualified_roles": len(qualified),
        "transferable_roles": len(transferable),
        "stretch_roles": len(stretch),
        "remote_from_india": remote_india,
        "remote_from_europe": remote_europe,
        "eor_possible": eor,
        "visa_sponsorship": visa,
        "relocation_support": relocation,
        "why_targeted": why,
        "relevant_job_ids": [j["id"] for j in relevant][:20],
    }

def compute_all_company_fit(profile):
    """Recompute and persist company fit for every company against the current job registry.
    Matches jobs to companies by exact-lowercased-name (the same key the discovery adapters
    already normalize into company.name / job.company)."""
    from ..db import companies, jobs, conn
    all_jobs=jobs(10000)
    by_company={}
    for j in all_jobs:
        by_company.setdefault((j.get("company") or "").strip().lower(),[]).append(j)
    updated=0
    c=conn()
    for co in companies(5000):
        cjobs=by_company.get((co.get("name") or "").strip().lower(),[])
        fit=assess_company_fit(co,cjobs,profile)
        c.execute("UPDATE companies SET company_fit_detail=? WHERE id=?",(json.dumps(fit,ensure_ascii=False),co["id"]))
        updated+=1
    c.commit(); c.close()
    return updated
