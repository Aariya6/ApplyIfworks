from pathlib import Path
import json, shutil
ROOT=Path(__file__).resolve().parents[2]
PROFILE=ROOT/"config/profile.json"

def setup(force=False):
    if PROFILE.exists() and not force:
        return {"status":"READY","message":"Profile already exists. Use --force only to rebuild it."}
    PROFILE.parent.mkdir(parents=True,exist_ok=True)
    data={"candidate":{},"preferences":{},"education":[],"experience":[],"projects":[],"skills":{},"certifications":[],"hackathons":[],"factuality_policy":"Never invent facts; only use approved profile data."}
    prompts=[
      ("name","Full name"),("email","Email"),("phone","Phone"),("city","Current city/country"),("linkedin","LinkedIn URL"),("github","GitHub URL"),("notice_period","Notice period / availability")]
    for key,label in prompts:
        data["candidate"][key]=input(f"{label}: ").strip()
    data["candidate"]["work_authorization"]=input("Work authorization summary: ").strip()
    data["candidate"]["languages"]={"English":input("English level: ").strip(),"German":input("German level (or N/A): ").strip()}
    countries=input("Target countries (comma-separated): ").strip()
    data["preferences"]={"regions":["Europe","EU","EEA","UK"],"target_countries":[x.strip() for x in countries.split(',') if x.strip()],"remote_required":True,"full_time_required":True,"exclude_titles":["Sales","Account Executive","Business Development Representative","Cold Caller","Telemarketer"],"preferred_domains":["AI","Machine Learning","Software Engineering","Data","Cloud","AI Product","Technical Program Management","Developer Relations","Technical Writing","Responsible AI","AI Education","Research Engineering"],"preferred_salary_eur":60000,"daily_review_target":40}
    PROFILE.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    return {"status":"CREATED","path":str(PROFILE)}
