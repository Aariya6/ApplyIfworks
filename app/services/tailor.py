from pathlib import Path
import json,hashlib,re,datetime,html as htmlmod
from ..db import create_application,get_job,update_application,save_artifact,log_event
from ..models import json_hash
from .scoring import role_family
ROOT=Path(__file__).resolve().parents[2]
HEADINGS=["PROFESSIONAL SUMMARY","EDUCATION","TECHNICAL SKILLS","EXPERIENCE & LEADERSHIP","PROJECTS","CERTIFICATIONS","HACKATHONS","LANGUAGE PROFICIENCY"]
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load_profile(): return json.loads((ROOT/"config/profile.json").read_text(encoding="utf-8"))
def jd_keywords(text):
    words=re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}",text.lower()); stop={"the","and","for","with","from","that","this","you","your","our","are","will","have","has","job","role","work","team","into","they","their","what","who","how","all","can","not","but","about","using","years","year"}; counts={}
    for w in words:
        if w not in stop: counts[w]=counts.get(w,0)+1
    return [w for w,_ in sorted(counts.items(),key=lambda x:(-x[1],x[0]))[:100]]
def _background_phrase(profile):
    """Builds the summary's opening frame from the profile's own education entry instead of
    assuming every user is a Computer Science undergraduate -- that was hardcoded here before and
    would have misdescribed anyone using this project with a different background."""
    edu=(profile.get("education") or [None])[0]
    if edu and edu.get("degree"): return f"Candidate with a {edu['degree']} background"
    return "Candidate"
def _deterministic_summary(profile,job,top_skills,top_exp):
    title=job.get("title") or "this role"; company=job.get("company") or "your team"
    bg=_background_phrase(profile)
    if top_exp:
        bullet=(top_exp.get("bullets") or [""])[0].rstrip(".")
        return f"{bg} whose work at {top_exp.get('company','')} — {bullet.lower()} — lines up directly with the {title} opening at {company}."
    if top_skills:
        return f"{bg} with hands-on {', '.join(top_skills[:3])} experience, applying directly to what {company}'s {title} role is asking for."
    skills_blob=", ".join(sum(profile.get("skills",{}).values(),[])[:4])
    return f"{bg} applying for {title} at {company}" + (f", with hands-on {skills_blob} experience." if skills_blob else ".")

def build_strategy(profile,job):
    text=job.get("description",""); kws=jd_keywords(text); rf=role_family(job.get("title",""),text)
    facts=[]
    for e in profile["experience"]: facts.append(("experience",e,json.dumps(e).lower()))
    for p in profile["projects"]: facts.append(("project",p,json.dumps(p).lower()))
    scored=[]
    for kind,item,blob in facts: scored.append((sum(1 for k in kws if k in blob),kind,item))
    scored.sort(key=lambda x:-x[0])
    priority_skills=[k for k in kws if any(k in s.lower() for s in sum(profile["skills"].values(),[]))][:25]
    priority_experience=[x[2] for x in scored if x[1]=="experience"][:4]
    top_exp=priority_experience[0] if priority_experience and scored[0][0]>0 else None
    return {"role_family":rf,"priority_skills":priority_skills,"priority_experience":priority_experience,"priority_projects":[x[2] for x in scored if x[1]=="project"][:4],"keywords_supported":[k for k in kws if k in json.dumps(profile).lower()],"keywords_missing":[k for k in kws if k not in json.dumps(profile).lower()][:50],"claims_forbidden":[k for k in kws if k not in json.dumps(profile).lower()][:50],"tailored_summary":_deterministic_summary(profile,job,priority_skills,top_exp)}
def render_html(profile,job,strategy,template="ATS_MODERN"):
    exp=strategy["priority_experience"] or profile["experience"]; projs=strategy["priority_projects"] or profile["projects"]
    skills=[]
    for group,vals in profile["skills"].items(): skills.append(f"<strong>{htmlmod.escape(group)}:</strong> {htmlmod.escape(', '.join(vals))}")
    exhtml="".join(f"<section><h2>{htmlmod.escape(e['title'])} — {htmlmod.escape(e['company'])}</h2><div class='meta'>{htmlmod.escape(e['start'])} – {htmlmod.escape(e['end'])} · {htmlmod.escape(e['location'])}</div><ul>{''.join('<li>'+htmlmod.escape(b)+'</li>' for b in e['bullets'])}</ul></section>" for e in exp)
    prhtml="".join(f"<section><h2>{htmlmod.escape(p['name'])}</h2><div class='meta'>{htmlmod.escape(', '.join(p['stack']))}</div><ul>{''.join('<li>'+htmlmod.escape(b)+'</li>' for b in p['bullets'])}</ul></section>" for p in projs)
    edhtml="".join(f"<section><h2>{htmlmod.escape(e['institution'])}</h2><div class='meta'>{htmlmod.escape(e['degree'])} · {htmlmod.escape(e['start'])} – {htmlmod.escape(e['end'])} · {htmlmod.escape(e['location'])}</div><p>{htmlmod.escape(e.get('details',''))}</p></section>" for e in profile["education"][:1])
    ts=strategy.get("tailored_summary")
    # _deterministic_summary (tailor.build_strategy's tailored_summary) always returns a
    # non-empty, profile-driven string -- this is only a last-resort safety net, not a real
    # fallback path, so it must not assume any particular background the way a hardcoded
    # per-role-family dict of biographies used to.
    summary=ts if isinstance(ts,str) and ts.strip() else _background_phrase(profile)
    certs="<br>".join(htmlmod.escape(x) for x in profile["certifications"])
    hacks="<br>".join(htmlmod.escape(x) for x in profile["hackathons"])
    langs=" · ".join(f"{htmlmod.escape(k)}: {htmlmod.escape(v)}" for k,v in profile["candidate"]["languages"].items())
    skills_html="<br>".join(skills)
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>@page{{size:A4;margin:14mm 15mm}}body{{font-family:Arial,Helvetica,sans-serif;color:#111;font-size:9.5pt;line-height:1.32;margin:0}}h1{{font-size:20pt;margin:0 0 2px}}h2{{font-size:10.5pt;margin:9px 0 2px;border-bottom:1px solid #aaa;padding-bottom:2px}}p{{margin:3px 0}}ul{{margin:3px 0 5px;padding-left:16px}}li{{margin:1px 0}}.meta{{font-size:8.5pt;color:#444}}.contact{{font-size:8.5pt;margin-bottom:7px}}.summary{{margin:5px 0 7px}}section{{break-inside:avoid}}strong{{font-weight:700}}</style></head><body><h1>{htmlmod.escape(profile["candidate"]["name"])}</h1><div class="contact">{htmlmod.escape(profile["candidate"]["phone"])} · {htmlmod.escape(profile["candidate"]["email"])} · {htmlmod.escape(profile["candidate"]["city"])} · {htmlmod.escape(profile["candidate"]["linkedin"])}</div><p class="summary"><strong>SUMMARY</strong><br>{htmlmod.escape(summary)}</p><h2>EDUCATION</h2>{edhtml}<h2>TECHNICAL SKILLS</h2><p>{skills_html}</p><h2>EXPERIENCE & LEADERSHIP</h2>{exhtml}<h2>PROJECTS</h2>{prhtml}<h2>CERTIFICATIONS</h2><p>{certs}</p><h2>HACKATHONS</h2><p>{hacks}</p><h2>LANGUAGE PROFICIENCY</h2><p>{langs}</p></body></html>'''
def factuality_check(html,profile):
    facts=json.dumps(profile,ensure_ascii=False).lower(); flags=[]
    for token in ["amazon","google","meta","openai","anthropic","microsoft"]:
        if token in html.lower() and token not in facts: flags.append(token)
    return ("REVIEW" if flags else "PASS"),flags
def tailor(job_id,template="ATS_MODERN"):
    job=get_job(job_id); profile=load_profile();
    if not job: raise ValueError("Unknown job")
    aid=create_application(job_id); base=ROOT/"data/applications"/aid/"resume"; base.mkdir(parents=True,exist_ok=True)
    versions=sorted([p for p in base.glob("v*") if p.is_dir()]); version=f"v{len(versions)+1}"; out=base/version; out.mkdir()
    strategy=build_strategy(profile,job)
    try:
        from .llm import generate_strategy
        strategy,generation_mode=generate_strategy(profile,job,strategy)
    except Exception:
        generation_mode="deterministic-fallback"
    html=render_html(profile,job,strategy,template); (out/"tailored_resume.html").write_text(html,encoding="utf-8")
    from .documents import html_to_pdf,make_docx
    html_to_pdf(out/"tailored_resume.html",out/"tailored_resume.pdf"); make_docx(profile,job,out/"tailored_resume.docx")
    from .ats import pdf_text,ats_report,audit_pdf
    extracted=pdf_text(out/"tailored_resume.pdf"); ar=ats_report(extracted,job.get("description","") or ""); factuality,banned=factuality_check(html,profile)
    report={**ar,"factuality_status":factuality,"factuality_flags":banned,"strategy":strategy,"template":template,"pdf_audit":audit_pdf(out/"tailored_resume.pdf",profile)}
    (out/"tailoring_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    meta={"application_id":aid,"job_id":job_id,"version":version,"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"master_resume_hash":json_hash(profile),"job_description_hash":json_hash(job.get("description","")),"generation_model":generation_mode,"generation_prompt_version":"2.1","pdf_hash":sha(out/"tailored_resume.pdf"),"docx_hash":sha(out/"tailored_resume.docx"),"keyword_coverage":ar["keyword_coverage"],"factuality_status":factuality}
    (out/"metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    for p,kind in [(out/"tailored_resume.pdf","resume_pdf"),(out/"tailored_resume.docx","resume_docx"),(out/"tailored_resume.html","resume_html"),(out/"tailoring_report.json","tailoring_report")]: save_artifact(aid,kind,version,str(p),sha(p))
    update_application(aid,status="TAILORED",resume_version=version,resume_hash=meta["pdf_hash"]); log_event(aid,"TAILORED",version)
    return aid,version,report
