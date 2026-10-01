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
    if ats=="workday":
        # Real Workday career-site hostnames look like tenant.wd5.myworkdayjobs.com, with the
        # actual job-board "site" name as a path segment (often after a locale like en-US) --
        # confirmed live against nvidia.wd5.myworkdayjobs.com/en-US/NVIDIAExternalCareerSite and
        # fractal.wd1.myworkdayjobs.com/Careers. Composite slug carries all three pieces the
        # Workday adapter needs, since this project's ATS dispatch only passes one slug string.
        m=re.match(r'^([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com$',host)
        if not m: return ""
        tenant,wd=m.group(1),m.group(2)
        parts=[p for p in path if p and p.lower() not in {"en-us","en-gb","de-de","fr-fr"}]
        site=parts[-1] if parts else ""
        return f"{tenant}|{wd}|{site}" if site else ""
    return ""
