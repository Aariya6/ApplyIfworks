import requests, re
import xml.etree.ElementTree as ET
from .base import SourceAdapter, clean_html
from ..models import Job

HEADERS={"User-Agent":"RemoteJobPilot/1.0 (public job discovery; contact local user)"}

def req(url, timeout=8):
    r=requests.get(url,headers=HEADERS,timeout=timeout); r.raise_for_status(); return r

class RemoteOK(SourceAdapter):
    name="remoteok"
    def fetch(self, config):
        data=req(config["url"]).json(); out=[]
        for x in data if isinstance(data,list) else []:
            if not x.get("position"): continue
            title=x.get("position",""); company=x.get("company",""); url=x.get("url") or x.get("apply_url") or ""
            out.append(Job(Job.stable_id(company,title,x.get("location", "Remote"),url),title,company,x.get("location","Remote"),"remote","full-time",x.get("date",""),clean_html(x.get("description","")),self.name,url,url,x.get("salary", ""),"unknown",x))
        return out

class ArbeitNow(SourceAdapter):
    name="arbeitnow"
    def fetch(self, config):
        data=req(config["url"]).json(); out=[]
        for x in data.get("data",[]):
            title=x.get("title",""); company=x.get("company_name",""); url=x.get("url","")
            loc=x.get("location",""); remote="remote" if x.get("remote") else "unknown"
            out.append(Job(Job.stable_id(company,title,loc,url),title,company,loc,remote,"full-time",x.get("created_at",""),clean_html(x.get("description","")),self.name,url,url,"","unknown",x))
        return out

class Remotive(SourceAdapter):
    name="remotive"
    def fetch(self, config):
        data=req(config["url"]).json(); out=[]
        for x in data.get("jobs",[]):
            title=x.get("title",""); company=x.get("company_name",""); url=x.get("url","")
            loc=x.get("candidate_required_location","")
            out.append(Job(Job.stable_id(company,title,loc,url),title,company,loc,"remote","full-time",x.get("publication_date",""),clean_html(x.get("description","")),self.name,url,url,x.get("salary", ""),"unknown",x))
        return out

class RSS(SourceAdapter):
    name="rss"
    def fetch(self, config):
        out=[]
        for url in config.get("urls",[]):
            xml=req(url).text
            root=ET.fromstring(xml)
            for item in root.findall('.//item'):
                title=(item.findtext('title') or '').strip(); link=(item.findtext('link') or '').strip(); desc=clean_html(item.findtext('description') or ''); company=''
                pub=(item.findtext('pubDate') or '').strip()
                out.append(Job(Job.stable_id(company,title,"",link),title,company,"","remote","unknown",pub,desc,self.name,url,link,"","unknown",{}))
        return out
