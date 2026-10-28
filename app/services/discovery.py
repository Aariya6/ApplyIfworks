from pathlib import Path
import yaml, json, datetime
from concurrent.futures import ThreadPoolExecutor
from ..db import upsert_job, save_source_health, find_job_identity, update_job_fit
from ..adapters.router import run_source_report
from .scoring import score_job, fit_tier
from .job_intelligence import work_auth,eligibility_for_india,extract_salary,infer_country,country_fit
from .eligibility import assess_eligibility
ROOT = Path(__file__).resolve().parents[2]

def _run_one(name, cfg):
    return run_source_report(name, cfg)

def _enabled_sources(cfg):
    out=[]
    for name,c in cfg["sources"].items():
        if not c.get("enabled"): continue
        sites=c.get("sites")
        if sites:
            for site in sites:
                merged={k:v for k,v in c.items() if k!="sites"}
                merged.update(site)
                merged["sites"]=[site]
                out.append((site.get("name",name),merged))
        else:
            out.append((name,c))
    return out

def discover():
    cfg = yaml.safe_load((ROOT/"config/sources.yaml").read_text(encoding="utf-8"))
    profile = json.loads((ROOT/"config/profile.json").read_text(encoding="utf-8"))
    total = 0; errors = []
    enabled = _enabled_sources(cfg)
    with ThreadPoolExecutor(max_workers=min(10,max(1,len(enabled)))) as ex:
        future_map = {name: (ex.submit(_run_one,name,c), c) for name,c in enabled}
        for name,(future,c) in future_map.items():
            try:
                found, adapter_failures = future.result(timeout=float(c.get("run_timeout_seconds",c.get("timeout",20))))
                seen=set(); good_jd=good_apply=0
                for j in found:
                    existing=find_job_identity(j.company,j.title,j.location)
                    if existing and existing.get("description") and len(existing.get("description","")) >= len(j.description or ""):
                        continue
                    d=j.to_dict(); score,reasons,fam,fr=score_job(d,profile); j.fit_score=score; j.role_family=fam; j.application_friction=fr; j.work_auth=work_auth(j.description,j.location); j.eligibility=eligibility_for_india(j.work_auth); j.salary_data=extract_salary(j.salary or j.description).to_dict(); j.canonical_url=j.apply_url; j.country=infer_country(j.title+' '+j.description,j.location); j.country_fit=country_fit(j.country,profile.get('preferences',{})); j.source_category=j.raw.get('category','') if isinstance(j.raw,dict) else c.get('category','')
                    upsert_job(j); seen.add(j.id); good_jd += bool(j.description); good_apply += bool(j.apply_url)
                    try: update_job_fit(j.id, fit_tier(score,fam,reasons), assess_eligibility(d,profile))
                    except Exception: pass
                total += len(found)
                failure_reason="; ".join(
                    f"{failure.get('company', failure.get('profile', name))}:{failure.get('error_type', 'source failure')}"
                    for failure in adapter_failures
                )
                if failure_reason:
                    errors.append((name, failure_reason))
                status=(
                    "FAIL" if adapter_failures and not found
                    else "PARTIAL" if adapter_failures or (found and not (good_jd and good_apply))
                    else "PASS" if found
                    else "ZERO_RESULT"
                )
                save_source_health(name,capability=c.get("capability","UNKNOWN"),search_supported=1,jd_supported=int(bool(found) and good_jd>0),application_url_supported=int(bool(found) and good_apply>0),last_tested=datetime.datetime.now(datetime.timezone.utc).isoformat(),status=status,failure_reason=failure_reason or ("" if found else "No jobs returned"),jobs_found=len(found),jd_success_rate=(good_jd/len(found)*100 if found else 0),application_success_rate=(good_apply/len(found)*100 if found else 0),duplicate_rate=((len(found)-len(seen))/len(found)*100 if found else 0))
            except Exception as e:
                errors.append((name,str(e))); save_source_health(name,capability=c.get("capability","UNKNOWN"),last_tested=datetime.datetime.now(datetime.timezone.utc).isoformat(),status="FAIL",failure_reason=str(e))
    return total, errors

def score_all():
    from ..db import jobs
    from ..models import Job
    profile=json.loads((ROOT/"config/profile.json").read_text(encoding="utf-8")); out=[]
    for d in jobs(5000):
        s,r,fam,fr=score_job(d,profile); d.update(fit_score=s,role_family=fam,application_friction=fr,work_auth=work_auth(d.get("description", ""),d.get("location", "")))
        d["eligibility"]=eligibility_for_india(d["work_auth"]); d["country"]=infer_country(d.get('title','')+' '+d.get('description',''),d.get('location','')); d["country_fit"]=country_fit(d["country"],profile.get('preferences',{})); d["salary_data"]=extract_salary(d.get("salary") or d.get("description", "")).to_dict()
        upsert_job(Job(**{k:d.get(k) for k in Job.__dataclass_fields__}))
        try: update_job_fit(d["id"], fit_tier(s,fam,r), assess_eligibility(d,profile))
        except Exception: pass
        out.append((s,r,d["id"]))
    return sorted(out,reverse=True)
