from pypdf import PdfReader
from pathlib import Path
import re

def pdf_text(path): return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
def audit_pdf(path,profile=None,job=None):
    text=pdf_text(path); issues=[]
    cand=(profile or {}).get("candidate",{})
    # Checks the actual candidate's own name/email/phone from their profile -- this used to be a
    # hardcoded name/email/phone literal, which would have silently audited every other user's
    # résumé against someone else's contact details.
    expected=[v for v in [cand.get("name"),cand.get("email"),cand.get("phone")] if v]+["EDUCATION","EXPERIENCE","SKILLS"]
    for field in expected:
        if field.lower() not in text.lower(): issues.append(f"missing extractable field: {field}")
    if not text.strip(): issues.append("no extractable text")
    return {"extractable_chars":len(text),"issues":issues,"pass":not issues,"single_column_expected":True}

def ats_report(resume_text,jd_text):
    jd=re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{2,}",jd_text.lower()); stop={"the","and","for","with","this","that","you","your","our","from","are","will","have","role","work","team","years","year"}
    kws=[]
    for x in jd:
        if x not in stop and x not in kws:kws.append(x)
    r=resume_text.lower(); matched=[x for x in kws if x in r]; missing=[x for x in kws if x not in r]
    return {"keyword_coverage":round(100*len(matched)/max(1,len(kws)),1),"matched_keywords":matched,"missing_keywords":missing[:80],"keyword_count":len(kws),"note":"Heuristic ATS/readability analysis; not an employer ATS score."}
