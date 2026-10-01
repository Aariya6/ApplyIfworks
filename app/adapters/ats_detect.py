from urllib.parse import urlparse
import re
PATTERNS={
 "greenhouse":["boards.greenhouse.io","job-boards.greenhouse.io","greenhouse.io/"],
 "lever":["jobs.lever.co","api.lever.co"],
 "ashby":["jobs.ashbyhq.com","ashbyhq.com/"],
 "workable":["apply.workable.com","workable.com/"],
 "smartrecruiters":["jobs.smartrecruiters.com","smartrecruiters.com/"],
 "personio":["jobs.personio.com","personio.com/"],
 "teamtailor":["teamtailor.com/"],
 "recruitee":["recruitee.com/"],
 "workday":["myworkdayjobs.com","workday.com/"],
 "icims":["icims.com/","careers-"],
 "successfactors":["successfactors.com","successfactors.eu"],
 "taleo":["taleo.net"],
}
def detect_ats(url,html=""):
    u=(url or "").lower(); h=(html or "").lower()
    for ats,terms in PATTERNS.items():
        if any(t in u or t in h for t in terms): return ats
    return "unknown"

def extract_ats_slug(url,ats):
    u=urlparse(url)
    host=u.netloc.lower(); path=u.path.strip('/').split('/')
    if ats=="greenhouse" and path: return path[0]
    if ats=="lever" and path: return path[0]
    if ats=="smartrecruiters" and "companies" in path:
        i=path.index("companies"); return path[i+1] if i+1<len(path) else ""
    if ats=="ashby" and path: return path[0]
    if ats=="workable" and path and path[0] not in {"j",""}: return path[0]
    return ""
