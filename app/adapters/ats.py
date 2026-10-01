import requests, re
from .base import ATSAdapter, clean_html
from ..models import Job

HEADERS={"User-Agent":"RemoteJobPilot/1.0 (public job discovery)"}

def get(url):
    r=requests.get(url,headers=HEADERS,timeout=8); r.raise_for_status(); return r.json()

class Greenhouse(ATSAdapter):
    name="greenhouse"
    def discover(self, company):
        data=get(f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true")
        out=[]
        for x in data.get("jobs",[]):
            title=x.get("title",""); url=x.get("absolute_url",""); loc=(x.get("location") or {}).get("name","")
            desc=clean_html((x.get("content") or ""));
            out.append(Job(Job.stable_id(company,title,loc,url),title,company,loc,"unknown","unknown",x.get("updated_at", ""),desc,self.name,url,url,"","greenhouse",x))
        return out

class Lever(ATSAdapter):
    name="lever"
    def discover(self, company):
        data=get(f"https://api.lever.co/v0/postings/{company}?mode=json")
        out=[]
        for x in data if isinstance(data,list) else []:
            title=x.get("text",""); url=x.get("hostedUrl") or x.get("applyUrl",""); loc=(x.get("categories") or {}).get("location","")
            desc=clean_html(x.get("descriptionPlain","") or x.get("description",""));
            out.append(Job(Job.stable_id(company,title,loc,url),title,company,loc,"unknown","unknown",x.get("createdAt", ""),desc,self.name,url,url,"","lever",x))
        return out

class SmartRecruiters(ATSAdapter):
    name="smartrecruiters"
    def discover(self, company):
        url=f"https://api.smartrecruiters.com/v1/companies/{company}/postings"
        data=get(url); out=[]
        for x in data.get("content",[]):
            title=x.get("name",""); url=(x.get("ref",{}) or {}).get("jobAd","")
            loc=((x.get("location") or {}).get("city","") or "")
            out.append(Job(Job.stable_id(company,title,loc,url),title,company,loc,"unknown","unknown",x.get("releasedDate",""),"",self.name,url,url,"","smartrecruiters",x))
        return out
