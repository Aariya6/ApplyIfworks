import os, requests
from .base import SourceAdapter, clean_html
from ..models import Job
class SerpAPI(SourceAdapter):
    name="serpapi"
    def fetch(self, config):
        key=os.getenv("SERPAPI_API_KEY")
        if not key: return []
        queries=config.get("queries", ["AI Engineer remote Europe"])
        out=[]
        for q in queries:
            r=requests.get(config["url"],params={"engine":"google_jobs","q":q,"api_key":key},timeout=10); r.raise_for_status()
            data=r.json()
            for x in data.get("jobs_results",[]):
                company=x.get("company_name",""); title=x.get("title",""); loc=x.get("location",""); url=(x.get("apply_options") or [{}])[0].get("link","")
                out.append(Job(Job.stable_id(company,title,loc,url),title,company,loc,"remote" if "remote" in loc.lower() else "unknown",x.get("detected_extensions",{}).get("schedule_type","unknown"),x.get("detected_extensions",{}).get("posted_at",""),clean_html(x.get("description","")),self.name,x.get("share_link",url),url,"","unknown",x))
        return out
