from pathlib import Path
import sqlite3, json, datetime
from .models import Job

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"; DB=DATA/"remote_job_pilot.sqlite3"
SCHEMA="""
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY,title TEXT,company TEXT,location TEXT,remote TEXT,employment TEXT,posted_at TEXT,description TEXT,
 source TEXT,discovery_url TEXT,apply_url TEXT,salary TEXT,ats TEXT,raw_json TEXT,created_at TEXT,updated_at TEXT,
 role_family TEXT DEFAULT 'unknown',fit_score REAL DEFAULT 0,application_friction TEXT DEFAULT 'unknown',work_auth TEXT DEFAULT 'unknown',eligibility TEXT DEFAULT 'human_review',salary_data TEXT,canonical_url TEXT DEFAULT '', country TEXT DEFAULT '', country_fit TEXT DEFAULT 'unknown', source_category TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS applications(
 id TEXT PRIMARY KEY,job_id TEXT,status TEXT,resume_version TEXT,resume_hash TEXT,letter_version TEXT,created_at TEXT,updated_at TEXT,
 submitted_at TEXT,evidence_path TEXT,notes TEXT,submitted_resume_version TEXT,submitted_resume_hash TEXT,submitted_resume_filename TEXT,
 FOREIGN KEY(job_id) REFERENCES jobs(id)
);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,application_id TEXT,event TEXT,detail TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS artifacts(id INTEGER PRIMARY KEY AUTOINCREMENT,application_id TEXT,kind TEXT,version TEXT,path TEXT,sha256 TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS qna(question TEXT PRIMARY KEY,answer TEXT,approved INTEGER DEFAULT 0,updated_at TEXT,category TEXT DEFAULT 'CUSTOM');
CREATE TABLE IF NOT EXISTS source_health(
 source TEXT PRIMARY KEY,capability TEXT,search_supported INTEGER DEFAULT 0,jd_supported INTEGER DEFAULT 0,application_url_supported INTEGER DEFAULT 0,
 last_tested TEXT,status TEXT,failure_reason TEXT,jobs_found INTEGER DEFAULT 0,jd_success_rate REAL DEFAULT 0,application_success_rate REAL DEFAULT 0,duplicate_rate REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS companies(
 id TEXT PRIMARY KEY,name TEXT,domain TEXT,website TEXT,careers_url TEXT,ats TEXT,country TEXT,city TEXT,remote_policy TEXT,hiring_regions TEXT,
 sector TEXT,discovered_from TEXT,last_checked TEXT,status TEXT,notes TEXT
);
CREATE TABLE IF NOT EXISTS screening_questions(
 id INTEGER PRIMARY KEY AUTOINCREMENT,application_id TEXT,question TEXT,category TEXT,confidence REAL,answer TEXT,status TEXT,source TEXT,created_at TEXT
);
CREATE TABLE IF NOT EXISTS application_evidence(
 id INTEGER PRIMARY KEY AUTOINCREMENT,application_id TEXT,kind TEXT,path TEXT,value TEXT,created_at TEXT
);
CREATE TABLE IF NOT EXISTS portfolio_projects(
 id TEXT PRIMARY KEY,name TEXT,target_job_family TEXT,required_skills TEXT,
 github_base_url TEXT,github_base_license TEXT,github_base_notes TEXT,
 improvements_plan TEXT,status TEXT DEFAULT 'IDEA',spec_markdown TEXT,
 repo_url TEXT,created_at TEXT,updated_at TEXT,notes TEXT,
 deployment_url TEXT,tech_stack TEXT,skills_demonstrated TEXT,target_skill_gaps TEXT,
 build_status TEXT DEFAULT 'NOT_STARTED',test_status TEXT DEFAULT 'NOT_STARTED',
 deployment_status TEXT DEFAULT 'NOT_STARTED',documentation_status TEXT DEFAULT 'NOT_STARTED',
 screenshot_status TEXT DEFAULT 'NOT_STARTED',readme_status TEXT DEFAULT 'NOT_STARTED',
 github_status TEXT DEFAULT 'NOT_STARTED',priority_score REAL DEFAULT 0,priority_reasons TEXT
);
CREATE TABLE IF NOT EXISTS skill_gap_signals(
 id INTEGER PRIMARY KEY AUTOINCREMENT,skill TEXT,job_count INTEGER,example_job_ids TEXT,computed_at TEXT
);
CREATE TABLE IF NOT EXISTS daily_application_log(
 day TEXT PRIMARY KEY,target INTEGER DEFAULT 0,discovered INTEGER DEFAULT 0,eligible INTEGER DEFAULT 0,
 qualified_count INTEGER DEFAULT 0,transferable_count INTEGER DEFAULT 0,official_career_page_count INTEGER DEFAULT 0,
 deep_personalization_count INTEGER DEFAULT 0,updated_at TEXT
);
"""

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def conn():
    DATA.mkdir(exist_ok=True);
    for name in ("applications","resumes","master","letters","exports","browser-profile","evidence"):
        (DATA/name).mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.executescript(SCHEMA)
    # Safe additive migrations for v1 databases.
    cols={r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()}
    for name,typ,default in [("role_family","TEXT","'unknown'"),("fit_score","REAL","0"),("application_friction","TEXT","'unknown'"),("work_auth","TEXT","'unknown'"),("canonical_url","TEXT","''"),("country","TEXT","''"),("country_fit","TEXT","'unknown'"),("source_category","TEXT","''"),("eligibility","TEXT","'human_review'"),("salary_data","TEXT","NULL"),("fit_tier","TEXT","'MISMATCH'"),("eligibility_detail","TEXT","NULL") ]:
        if name not in cols: c.execute(f"ALTER TABLE jobs ADD COLUMN {name} {typ} DEFAULT {default}")
    acols={r[1] for r in c.execute("PRAGMA table_info(applications)").fetchall()}
    for name,typ,default in [("submitted_resume_version","TEXT","NULL"),("submitted_resume_hash","TEXT","NULL"),("submitted_resume_filename","TEXT","NULL"),("application_method","TEXT","''"),
        ("human_required_reason","TEXT","NULL"),("automation_level","TEXT","NULL"),("personalization_level","TEXT","NULL"),("outcome_updated_at","TEXT","NULL"),
        ("source_channel","TEXT","''"),("rejection_reason","TEXT","''")]:
        if name not in acols: c.execute(f"ALTER TABLE applications ADD COLUMN {name} {typ} DEFAULT {default}")
    ccols={r[1] for r in c.execute("PRAGMA table_info(companies)").fetchall()}
    for name,typ,default in [("company_fit_detail","TEXT","NULL"),
        ("niche_domain","TEXT","''"),("geography_strategy","TEXT","''"),("personal_fit","TEXT","''"),
        ("ownership_potential","TEXT","''"),("india_eligibility_note","TEXT","''"),("target_role_families_note","TEXT","''"),
        ("why_target_note","TEXT","''"),("reference_search_url","TEXT","''")]:
        if name not in ccols: c.execute(f"ALTER TABLE companies ADD COLUMN {name} {typ} DEFAULT {default}")
    ppcols={r[1] for r in c.execute("PRAGMA table_info(portfolio_projects)").fetchall()}
    for name,typ,default in [("deployment_url","TEXT","''"),("tech_stack","TEXT","''"),("skills_demonstrated","TEXT","''"),
        ("target_skill_gaps","TEXT","''"),("build_status","TEXT","'NOT_STARTED'"),("test_status","TEXT","'NOT_STARTED'"),
        ("deployment_status","TEXT","'NOT_STARTED'"),("documentation_status","TEXT","'NOT_STARTED'"),
        ("screenshot_status","TEXT","'NOT_STARTED'"),("readme_status","TEXT","'NOT_STARTED'"),
        ("github_status","TEXT","'NOT_STARTED'"),("priority_score","REAL","0"),("priority_reasons","TEXT","NULL")]:
        if name not in ppcols: c.execute(f"ALTER TABLE portfolio_projects ADD COLUMN {name} {typ} DEFAULT {default}")
    c.commit(); return c

def upsert_job(job:Job):
    c=conn(); t=now(); d=job.to_dict()
    c.execute("""INSERT INTO jobs(id,title,company,location,remote,employment,posted_at,description,source,discovery_url,apply_url,salary,ats,raw_json,created_at,updated_at,role_family,fit_score,application_friction,work_auth,eligibility,salary_data,canonical_url,country,country_fit,source_category)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,company=excluded.company,location=excluded.location,remote=excluded.remote,
    employment=excluded.employment,posted_at=excluded.posted_at,description=excluded.description,source=excluded.source,discovery_url=excluded.discovery_url,apply_url=excluded.apply_url,
    salary=excluded.salary,ats=excluded.ats,raw_json=excluded.raw_json,updated_at=excluded.updated_at,role_family=excluded.role_family,fit_score=excluded.fit_score,
    application_friction=excluded.application_friction,work_auth=excluded.work_auth,eligibility=excluded.eligibility,salary_data=excluded.salary_data,canonical_url=excluded.canonical_url,country=excluded.country,country_fit=excluded.country_fit,source_category=excluded.source_category""",
    (job.id,job.title,job.company,job.location,job.remote,job.employment,job.posted_at,job.description,job.source,job.discovery_url,job.apply_url,job.salary,job.ats,json.dumps(job.raw or {},ensure_ascii=False),t,t,job.role_family,job.fit_score,job.application_friction,job.work_auth,job.eligibility,json.dumps(job.salary_data or {},ensure_ascii=False),job.canonical_url or job.apply_url,job.country,job.country_fit,job.source_category))
    c.commit(); c.close()

def update_job_fit(job_id,fit_tier,eligibility_detail):
    c=conn(); c.execute("UPDATE jobs SET fit_tier=?, eligibility_detail=? WHERE id=?",(fit_tier,json.dumps(eligibility_detail,ensure_ascii=False),job_id)); c.commit(); c.close()

def upsert_portfolio_project(id,**data):
    c=conn(); t=now()
    cols=["name","target_job_family","required_skills","github_base_url","github_base_license","github_base_notes","improvements_plan","status","spec_markdown","repo_url","notes",
        "deployment_url","tech_stack","skills_demonstrated","target_skill_gaps","build_status","test_status",
        "deployment_status","documentation_status","screenshot_status","readme_status","github_status","priority_score","priority_reasons"]
    existing=c.execute("SELECT id FROM portfolio_projects WHERE id=?",(id,)).fetchone()
    if existing:
        sets=", ".join(f"{k}=?" for k in cols if k in data); vals=[data[k] for k in cols if k in data]+[t,id]
        if sets: c.execute(f"UPDATE portfolio_projects SET {sets}, updated_at=? WHERE id=?",vals)
    else:
        allcols=["id"]+cols+["created_at","updated_at"]
        vals=[id]+[data.get(k,"") for k in cols]+[t,t]
        c.execute(f"INSERT INTO portfolio_projects({','.join(allcols)}) VALUES ({','.join('?' for _ in allcols)})",vals)
    c.commit(); c.close()

def portfolio_projects():
    c=conn(); rows=c.execute("SELECT * FROM portfolio_projects ORDER BY updated_at DESC").fetchall(); c.close(); return [dict(r) for r in rows]

def get_portfolio_project(id):
    c=conn(); r=c.execute("SELECT * FROM portfolio_projects WHERE id=?",(id,)).fetchone(); c.close(); return dict(r) if r else None

def save_skill_gap_signals(signals):
    """Replace the whole table each run — this is a point-in-time snapshot, not a log."""
    c=conn(); c.execute("DELETE FROM skill_gap_signals"); t=now()
    for s in signals:
        c.execute("INSERT INTO skill_gap_signals(skill,job_count,example_job_ids,computed_at) VALUES (?,?,?,?)",
            (s["skill"],s["job_count"],json.dumps(s.get("example_job_ids",[])),t))
    c.commit(); c.close()

def skill_gap_signals():
    c=conn(); rows=c.execute("SELECT * FROM skill_gap_signals ORDER BY job_count DESC").fetchall(); c.close(); return [dict(r) for r in rows]

def jobs(limit=500):
    c=conn(); rows=c.execute("SELECT * FROM jobs ORDER BY fit_score DESC,updated_at DESC LIMIT ?",(limit,)).fetchall(); c.close(); return [dict(r) for r in rows]
def get_job(job_id):
    c=conn(); r=c.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone(); c.close(); return dict(r) if r else None

def jobs_created_since(iso_timestamp,fit_tiers=("QUALIFIED","TRANSFERABLE")):
    c=conn()
    placeholders=",".join("?"*len(fit_tiers))
    rows=c.execute(f"SELECT * FROM jobs WHERE created_at>? AND fit_tier IN ({placeholders}) ORDER BY fit_score DESC",(iso_timestamp,*fit_tiers)).fetchall()
    c.close(); return [dict(r) for r in rows]

def find_job_identity(company,title,location):
    c=conn(); r=c.execute("SELECT * FROM jobs WHERE lower(company)=lower(?) AND lower(title)=lower(?) AND lower(location)=lower(?) LIMIT 1",(company,title,location)).fetchone(); c.close(); return dict(r) if r else None

def create_application(job_id):
    aid=f"app_{job_id}"; c=conn(); t=now(); c.execute("INSERT OR IGNORE INTO applications(id,job_id,status,created_at,updated_at) VALUES (?,?,?,?,?)",(aid,job_id,"DISCOVERED",t,t)); c.commit(); c.close(); return aid

def update_application(aid,**fields):
    if not fields:return
    allowed={"status","resume_version","resume_hash","letter_version","updated_at","submitted_at","evidence_path","notes","submitted_resume_version","submitted_resume_hash","submitted_resume_filename","application_method","human_required_reason","automation_level","personalization_level","outcome_updated_at","source_channel","rejection_reason"}
    fields={k:v for k,v in fields.items() if k in allowed}; fields["updated_at"]=now(); c=conn(); sets=", ".join(f"{k}=?" for k in fields); vals=list(fields.values())+[aid]; c.execute(f"UPDATE applications SET {sets} WHERE id=?",vals); c.commit(); c.close()
def get_application(aid):
    c=conn(); r=c.execute("SELECT * FROM applications WHERE id=?",(aid,)).fetchone(); c.close(); return dict(r) if r else None

def log_event(aid,event,detail=""):
    c=conn(); c.execute("INSERT INTO events(application_id,event,detail,created_at) VALUES (?,?,?,?)",(aid,event,detail,now())); c.commit(); c.close()
def applications(limit=500):
    c=conn(); rows=c.execute("SELECT a.*,j.title,j.company,j.apply_url,j.source,j.fit_score,j.fit_tier,j.application_friction FROM applications a JOIN jobs j ON j.id=a.job_id ORDER BY a.updated_at DESC LIMIT ?",(limit,)).fetchall(); c.close(); return [dict(r) for r in rows]

def applications_for_company(company_name):
    """FP10: every application tied to this company, for a company relationship ledger --
    long-term leverage comes from the accumulated history, not an isolated application."""
    c=conn()
    rows=c.execute("""SELECT a.*,j.title,j.fit_score,j.fit_tier FROM applications a JOIN jobs j ON j.id=a.job_id
        WHERE lower(j.company)=lower(?) ORDER BY a.updated_at DESC""",(company_name,)).fetchall()
    c.close(); return [dict(r) for r in rows]

def set_daily_target(target):
    day=now()[:10]; c=conn()
    c.execute("INSERT INTO daily_application_log(day,target,updated_at) VALUES (?,?,?) ON CONFLICT(day) DO UPDATE SET target=excluded.target,updated_at=excluded.updated_at",(day,target,now()))
    c.commit(); c.close()

def get_daily_log(day=None):
    day=day or now()[:10]; c=conn(); r=c.execute("SELECT * FROM daily_application_log WHERE day=?",(day,)).fetchone(); c.close()
    return dict(r) if r else {"day":day,"target":0,"discovered":0,"eligible":0,"qualified_count":0,"transferable_count":0,"official_career_page_count":0,"deep_personalization_count":0}

def daily_log_history(limit=30):
    c=conn(); rows=c.execute("SELECT * FROM daily_application_log ORDER BY day DESC LIMIT ?",(limit,)).fetchall(); c.close(); return [dict(r) for r in rows]

def record_discovery_counts(discovered,eligible):
    day=now()[:10]; c=conn()
    c.execute("INSERT INTO daily_application_log(day,discovered,eligible,updated_at) VALUES (?,?,?,?) ON CONFLICT(day) DO UPDATE SET discovered=excluded.discovered,eligible=excluded.eligible,updated_at=excluded.updated_at",(day,discovered,eligible,now()))
    c.commit(); c.close()
def save_artifact(aid,kind,version,path,sha256):
    c=conn(); c.execute("INSERT INTO artifacts(application_id,kind,version,path,sha256,created_at) VALUES (?,?,?,?,?,?)",(aid,kind,version,path,sha256,now())); c.commit(); c.close()
def save_source_health(source,**data):
    c=conn(); fields={"source":source,**data}; cols=["source","capability","search_supported","jd_supported","application_url_supported","last_tested","status","failure_reason","jobs_found","jd_success_rate","application_success_rate","duplicate_rate"]
    vals=[fields.get(k,0 if k.endswith("supported") or k in {"jobs_found"} else "") for k in cols]
    c.execute(f"INSERT INTO source_health({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) ON CONFLICT(source) DO UPDATE SET {','.join(f'{k}=excluded.{k}' for k in cols[1:])}",vals); c.commit(); c.close()
def source_health():
    c=conn(); rows=c.execute("SELECT * FROM source_health ORDER BY source").fetchall(); c.close(); return [dict(r) for r in rows]
def upsert_company(**data):
    c=conn(); cols=["id","name","domain","website","careers_url","ats","country","city","remote_policy","hiring_regions","sector","discovered_from","last_checked","status","notes",
        "niche_domain","geography_strategy","personal_fit","ownership_potential","india_eligibility_note","target_role_families_note","why_target_note","reference_search_url"]; vals=[data.get(k,"") for k in cols]
    c.execute(f"INSERT INTO companies({','.join(cols)}) VALUES ({','.join('?' for _ in cols)}) ON CONFLICT(id) DO UPDATE SET {','.join(f'{k}=excluded.{k}' for k in cols[1:])}",vals); c.commit(); c.close()
def companies(limit=1000):
    c=conn(); rows=c.execute("SELECT * FROM companies ORDER BY name LIMIT ?",(limit,)).fetchall(); c.close(); return [dict(r) for r in rows]
def get_company(company_id):
    c=conn(); r=c.execute("SELECT * FROM companies WHERE id=?",(company_id,)).fetchone(); c.close(); return dict(r) if r else None
def add_screening_question(aid,question,category,confidence,answer,status,source="browser"):
    c=conn(); c.execute("INSERT INTO screening_questions(application_id,question,category,confidence,answer,status,source,created_at) VALUES (?,?,?,?,?,?,?,?)",(aid,question,category,confidence,answer,status,source,now())); c.commit(); c.close()
def screening_questions(aid):
    c=conn(); rows=c.execute("SELECT * FROM screening_questions WHERE application_id=? ORDER BY id",(aid,)).fetchall(); c.close(); return [dict(r) for r in rows]
def add_evidence(aid,kind,path="",value=""):
    c=conn(); c.execute("INSERT INTO application_evidence(application_id,kind,path,value,created_at) VALUES (?,?,?,?,?)",(aid,kind,path,value,now())); c.commit(); c.close()


def get_qna(question):
    q=(question or '').strip()
    c=conn(); r=c.execute("SELECT * FROM qna WHERE lower(question)=lower(?)",(q,)).fetchone()
    if r:
        c.close(); return dict(r)
    rows=c.execute("SELECT * FROM qna WHERE approved=1").fetchall(); c.close()
    if not rows or not q: return None
    try:
        from rapidfuzz.fuzz import WRatio
        best=max(rows,key=lambda x: WRatio(q.lower(),x['question'].lower()))
        return dict(best) if WRatio(q.lower(),best['question'].lower()) >= 86 else None
    except Exception:
        return None

def save_qna(question,answer,approved=1,category="CUSTOM"):
    c=conn(); c.execute("INSERT INTO qna(question,answer,approved,updated_at,category) VALUES (?,?,?,?,?) ON CONFLICT(question) DO UPDATE SET answer=excluded.answer,approved=excluded.approved,updated_at=excluded.updated_at,category=excluded.category",(question.strip(),answer,int(approved),now(),category)); c.commit(); c.close()

def qnas():
    c=conn(); rows=c.execute("SELECT * FROM qna ORDER BY category,question").fetchall(); c.close(); return [dict(r) for r in rows]
