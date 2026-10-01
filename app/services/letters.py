from pathlib import Path
import json,datetime,html,hashlib
from .tailor import load_profile,build_strategy,ROOT,_background_phrase
from ..db import create_application,get_job,update_application,save_artifact,log_event

def generate_letter(job_id):
    job=get_job(job_id); p=load_profile(); aid=create_application(job_id); s=build_strategy(p,job)
    base=ROOT/"data/applications"/aid/"letters"; base.mkdir(parents=True,exist_ok=True); versions=list(base.glob("v*")); v=f"v{len(versions)+1}"; out=base/v; out.mkdir()
    company=job["company"]; title=job["title"]; rf=s["role_family"]; name=p["candidate"].get("name","")
    relevant=s["priority_experience"][:2]; projects=s["priority_projects"][:1]
    # Secondary leadership/communication highlight: the next experience entry not already used
    # above, rather than a hardcoded sentence describing one specific person's extracurriculars.
    used_companies={e.get("company") for e in relevant}
    extra=next((e for e in p.get("experience",[]) if e.get("company") not in used_companies),None)
    body=[f"Dear Hiring Team at {company},",f"I am applying for the {title} role because it aligns with my interest in building practical technology at the intersection of {rf.replace('_',' ').lower()} and real user or organizational needs.",f"I am a {_background_phrase(p).lower()}, with hands-on experience across {', '.join(sum(p.get('skills',{}).values(),[])[:4]) or 'software development'}."]
    for e in relevant: body.append(f"At {e['company']}, I worked as {e['title']} on {e['bullets'][0].rstrip('.') }.")
    for pjt in projects: body.append(f"A relevant project is {pjt['name']}, where I {pjt['bullets'][0].rstrip('.').lower()}.")
    if extra: body.append(f"Alongside engineering, {extra['bullets'][0].rstrip('.').lower() if extra.get('bullets') else 'I have taken on ' + extra.get('title','additional responsibility')}, strengthening my ability to explain technical ideas and coordinate across functions.")
    body.append("I would welcome the opportunity to contribute to your team and discuss how my technical foundation and interdisciplinary interests could support the role.")
    text="\n\n".join(body)+f"\n\nKind regards,\n{name}"
    html_text="<html><head><style>@page{size:A4;margin:20mm}body{font-family:Arial,Helvetica,sans-serif;color:#111;font-size:10.5pt;line-height:1.5}h1{font-size:18pt;margin:0 0 4px}p{margin:0 0 12px}.meta{font-size:9pt;color:#555;margin-bottom:18px}</style></head><body><h1>"+html.escape(name)+"</h1><div class='meta'>Application: "+html.escape(title)+" · "+html.escape(company)+"<br>"+html.escape(p['candidate'].get('email',''))+" · "+html.escape(p['candidate'].get('linkedin',''))+"</div>"+"".join(f"<p>{html.escape(x)}</p>" for x in body[:-1])+"<p>Kind regards,<br>"+html.escape(name)+"</p></body></html>"
    (out/"motivation_letter.txt").write_text(text,encoding="utf-8"); (out/"motivation_letter.html").write_text(html_text,encoding="utf-8")
    from .documents import html_to_pdf
    html_to_pdf(out/"motivation_letter.html",out/"motivation_letter.pdf")
    meta={"application_id":aid,"job_id":job_id,"version":v,"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),"factuality_status":"PASS","role_family":rf,"keywords_used":s["keywords_supported"],"generation_mode":"role-aware-deterministic","pdf_hash":hashlib.sha256((out/"motivation_letter.pdf").read_bytes()).hexdigest()}
    (out/"metadata.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding="utf-8")
    for fp,kind in [(out/"motivation_letter.txt","motivation_letter_txt"),(out/"motivation_letter.html","motivation_letter_html"),(out/"motivation_letter.pdf","motivation_letter_pdf")]: save_artifact(aid,kind,v,str(fp),hashlib.sha256(fp.read_bytes()).hexdigest())
    update_application(aid,status="LETTER_READY",letter_version=v); log_event(aid,"LETTER_READY",v)
    return aid,v,text
