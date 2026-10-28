import requests, re
import time
import xml.etree.ElementTree as ET
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
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
            title=x.get("position",""); company=x.get("company",""); url=x.get("url") or ""
            apply_url=x.get("apply_url") or ""
            out.append(Job(Job.stable_id(company,title,x.get("location", "Remote"),url),title,company,x.get("location","Remote"),"remote","full-time",x.get("date",""),clean_html(x.get("description","")),self.name,url,apply_url,x.get("salary", ""),"unknown",x))
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

class Jobicy(SourceAdapter):
    name="jobicy"
    def fetch(self, config):
        base_url=config["url"]
        max_pages=max(1,int(config.get("max_pages",3)))
        page_delay=max(0.0,float(config.get("page_delay_seconds",1.0)))
        out=[]
        cursor=None
        seen_cursors=set()
        for page_index in range(max_pages):
            page_url=_jobicy_page_url(base_url,cursor)
            data=req(page_url).json()
            if not isinstance(data,dict) or not isinstance(data.get("jobs"),list):
                raise ValueError("Jobicy API response did not contain a jobs list")
            for item in data["jobs"]:
                if not isinstance(item,dict):
                    continue
                title=str(item.get("jobTitle") or "").strip()
                company=str(item.get("companyName") or "").strip()
                url=str(item.get("url") or "").strip()
                if not title or not company or not url:
                    continue
                location=str(item.get("jobGeo") or "")
                job_types=item.get("jobType") or []
                employment=", ".join(str(value) for value in job_types) if isinstance(job_types,list) else str(job_types)
                salary_min=item.get("salaryMin")
                salary_max=item.get("salaryMax")
                salary_currency=str(item.get("salaryCurrency") or "")
                salary_period=str(item.get("salaryPeriod") or "")
                salary=""
                if salary_min is not None or salary_max is not None:
                    salary_range=" - ".join(str(value) for value in (salary_min,salary_max) if value is not None)
                    salary=" ".join(value for value in (salary_currency,salary_range,salary_period) if value)
                raw={**item,"id":item.get("id"),"url":url,"pubDate":item.get("pubDate","")}
                out.append(Job(
                    Job.stable_id(company,title,location,url),
                    title,
                    company,
                    location,
                    "remote",
                    employment or "unknown",
                    item.get("pubDate",""),
                    clean_html(item.get("jobDescription","")),
                    self.name,
                    url,
                    url,
                    salary,
                    "unknown",
                    raw,
                ))
            next_cursor=data.get("nextCursor")
            if not next_cursor or page_index + 1 >= max_pages or next_cursor in seen_cursors:
                break
            seen_cursors.add(next_cursor)
            cursor=next_cursor
            if page_delay:
                time.sleep(page_delay)
        return out


def _jobicy_page_url(url, cursor=None):
    if not cursor:
        return url
    parsed=urlsplit(url)
    query=dict(parse_qsl(parsed.query,keep_blank_values=True))
    query["cursor"]=cursor
    return urlunsplit((parsed.scheme,parsed.netloc,parsed.path,urlencode(query),parsed.fragment))

class WeWorkRemotelyRSS(SourceAdapter):
    name="weworkremotely"
    def fetch(self, config):
        root=ET.fromstring(req(config["url"]).text)
        out=[]
        for item in root.findall(".//item"):
            feed_title=(item.findtext("title") or "").strip()
            url=(item.findtext("link") or "").strip()
            if not feed_title or not url:
                continue
            company,title=feed_title,""
            if ": " in feed_title:
                company,title=feed_title.split(": ",1)
            else:
                title=feed_title
            region=(item.findtext("region") or "").strip()
            country=(item.findtext("country") or "").strip()
            state=(item.findtext("state") or "").strip()
            location=", ".join(value for value in (region,state,country) if value)
            employment=(item.findtext("type") or "").strip() or "unknown"
            description=clean_html(item.findtext("description") or "")
            raw={
                "title":title,
                "feed_title":feed_title,
                "company":company,
                "url":url,
                "pubDate":(item.findtext("pubDate") or "").strip(),
                "region":region,
                "country":country,
                "state":state,
            }
            out.append(Job(
                Job.stable_id(company,title,location,url),
                title,
                company,
                location,
                "remote",
                employment,
                raw["pubDate"],
                description,
                self.name,
                url,
                url,
                "",
                "unknown",
                raw,
            ))
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
                out.append(Job(Job.stable_id(company,title,"",link),title,company,"","remote","unknown",pub,desc,self.name,url,link,"","unknown",{"pubDate":pub}))
        return out
