"""Per-job application strategy: pulls together what's already known (résumé strategy, company
registry, skill-gap portfolio projects, eligibility) into one actionable packet. Every field is
either derived from real data already in this database, or explicitly marked unavailable — never
invented (no fabricated "networking contacts", no fake "why this company" copy about products we
don't actually have real data on).
"""
import json

INTERVIEW_TOPICS_BY_FAMILY={
    "AI_ENGINEERING":["Explain a real ML pipeline you built end to end (data → model → evaluation)","Trade-offs you made on a project (e.g. XGBoost vs. alternatives) and why","How you'd approach a task you haven't done before, given your internship experience"],
    "MLOPS_PLATFORM":["Basic deployment/CI-CD concepts, even if self-taught","How you'd monitor a system in production","Cloud fundamentals (whatever you've touched: GCP/AWS/Azure console)"],
    "DATA":["Walk through a real dataset you cleaned/analyzed and a decision you made about it","SQL fundamentals","How you validate a model isn't overfitting"],
    "SOFTWARE":["A project's architecture, and what you'd change if you rebuilt it","Debugging story — a real bug you tracked down","Your comfort with the specific stack this JD lists"],
    "AI_PRODUCT":["How you'd prioritize a roadmap with limited engineering capacity","A time you translated a technical constraint to a non-technical audience","What 'AI product' means to you specifically, grounded in a real project"],
    "PRODUCT_MANAGEMENT":["How you gather requirements without formal PM experience — draw on any real event/project planning you've done","A decision you made with incomplete information","How you'd measure success for a feature"],
    "PROGRAM_MANAGEMENT":["A real event/project-logistics or budget-management story from your own experience, in detail — dates, numbers, what went wrong and how you fixed it","How you keep multiple stakeholders aligned"],
    "DEVELOPER_RELATIONS":["Walk through a workshop or talk you've given — audience, content, what you'd improve","How you explain a technical concept to a non-expert","Your public-speaking/content experience, concretely"],
    "TECHNICAL_COMMUNICATION":["A piece of technical writing/documentation you're proud of","How you simplify without losing accuracy"],
    "COMMUNITY_OPERATIONS":["Your experience organizing/leading a group, from your own background — be ready with real numbers"],
    "AI_HUMANITIES":["Your view on a real AI-ethics tension, grounded in something you've actually read/worked on — never invent a position you haven't thought through"],
    "CONSULTING_SOLUTIONS":["A time you translated a technical solution for a business stakeholder"],
}

def _company_by_name(name):
    from ..db import companies
    name_l=(name or "").strip().lower()
    for c in companies(5000):
        if (c.get("name") or "").strip().lower()==name_l: return c
    return None

def build_application_strategy(job_id):
    from ..db import get_job, portfolio_projects
    from .tailor import build_strategy, load_profile
    job=get_job(job_id)
    if not job: raise ValueError("Unknown job")
    profile=load_profile()
    strategy=build_strategy(profile,job)

    company=_company_by_name(job.get("company",""))
    company_fit=None
    if company and company.get("company_fit_detail"):
        try: company_fit=json.loads(company["company_fit_detail"])
        except Exception: company_fit=None

    # Missing requirements: keywords the JD asks for that aren't in the candidate's profile —
    # reuses the same signal already computed for résumé tailoring, not a new guess.
    missing=strategy.get("keywords_missing",[])[:15]

    # Suggested portfolio project: match by target_job_family containing this job's role_family,
    # falling back to a required-skill overlap with the JD text. Never suggests a project with no
    # real connection to the job.
    role_family=job.get("role_family","")
    jd_text=(job.get("title","")+" "+job.get("description","")).lower()
    best_project=None; best_score=0
    for proj in portfolio_projects():
        score=0
        if role_family and role_family in (proj.get("target_job_family") or ""): score+=3
        for skill in (proj.get("required_skills") or "").split(","):
            skill=skill.strip().lower()
            if skill and skill in jd_text: score+=1
        if score>best_score: best_score=score; best_project=proj
    suggested_project = {"id":best_project["id"],"name":best_project["name"],"status":best_project["status"],"reason":f"role-family/skill overlap score {best_score}"} if best_project and best_score>0 else None

    talking_points=[]
    if company_fit:
        if company_fit.get("ai_product_relevance")=="HIGH": talking_points.append("AI/ML is a stated theme across their open roles — reference specifically which of their listed technologies you've used.")
        if (company.get("ats") or "") in {"greenhouse","lever","ashby","workable","smartrecruiters"}: talking_points.append(f"Applying through their official {company['ats']} board (not a scraped aggregator) — mention you found the role directly on their careers page.")
    if company and company.get("remote_policy"): talking_points.append(f"Registry notes remote policy: {company['remote_policy']}")
    if not talking_points: talking_points.append("No enriched company research available beyond the job posting itself — read the actual JD closely before the interview; this registry does not have deep company/product data for every entry.")

    topics=INTERVIEW_TOPICS_BY_FAMILY.get(role_family,["Review the JD line by line and prepare one concrete example per requirement — do not improvise on unfamiliar claims."])

    return {
        "job_id":job_id,
        "role":job.get("title"),
        "company":job.get("company"),
        "resume_role_family":role_family,
        "strongest_experience":[e.get("title") for e in strategy.get("priority_experience",[])[:2]],
        "strongest_projects":[p.get("name") for p in strategy.get("priority_projects",[])[:2]],
        "missing_requirements":missing,
        "company_talking_points":talking_points,
        "networking_targets":"Not available — this system has no LinkedIn/employee-directory data source. Manual research recommended (search the company name + role on LinkedIn).",
        "suggested_portfolio_project":suggested_project,
        "interview_prep_topics":topics,
        "application_url":job.get("apply_url"),
        "company_fit_summary":company_fit,
    }
