"""Config-driven, source-aware public job-board ingestion.

This is intentionally not the old generic link scanner. Each source has a profile
(URLs, selectors, title/link patterns, category and access mode). Extraction prefers
JSON-LD JobPosting, then source selectors, then constrained job links. No login,
CAPTCHA bypass or anti-bot evasion is attempted.
"""
import json, re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from .base import SourceAdapter, clean_html
from ..models import Job

UA = "RemoteJobPilot/4.0 (+public job discovery; source-specific parser)"


def _text(node):
    return clean_html(node.get_text(" ", strip=True) if node else "")


def _first(node, selectors):
    for s in selectors or []:
        x = node.select_one(s)
        if x: return x
    return None


def _attr(node, names):
    if not node: return ""
    for n in names:
        v = node.get(n)
        if v: return str(v).strip()
    return ""


def _jsonld(soup):
    out=[]
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            obj=json.loads(tag.string or tag.get_text())
            vals=obj if isinstance(obj,list) else obj.get("@graph",[]) if isinstance(obj,dict) else []
            if isinstance(obj,dict) and obj.get("@type")=="JobPosting": vals=[obj]
            for x in vals:
                if isinstance(x,dict) and (x.get("@type")=="JobPosting" or "JobPosting" in (x.get("@type") or [])):
                    out.append(x)
        except Exception:
            pass
    return out


def _salary(v):
    if not v: return ""
    if isinstance(v,str): return v
    if isinstance(v,dict):
        if "value" in v:
            val=v["value"]
            if isinstance(val,dict):
                a=val.get("minValue",val.get("value","")); b=val.get("maxValue","")
                cur=v.get("currency","")
                return f"{cur} {a}-{b}".strip(" -")
            return f"{v.get('currency','')} {val}".strip()
        return str(v)
    return str(v)


class CatalogHTML(SourceAdapter):
    name="catalog_html"
    def fetch(self, config):
        out=[]
        for profile in config.get("sites",[]):
            out.extend(self._site(profile))
        return out

    def _site(self, p):
        if p.get("access_mode")=="LINK_ONLY": return []
        first_url=p["url"]
        jobs=[]
        seen_pages=set()
        max_pages=int(p.get("max_pages", 2))
        next_url=first_url
        for _ in range(max_pages):
            if not next_url or next_url in seen_pages: break
            seen_pages.add(next_url)
            page_jobs, next_url=self._parse_page(p,next_url)
            jobs.extend(page_jobs)
        return self._dedupe(jobs)

    def _parse_page(self,p,url):
        try:
            r=requests.get(url,headers={"User-Agent":UA,"Accept-Language":"en-US,en;q=0.9"},timeout=float(p.get("timeout",20)),allow_redirects=True)
            r.raise_for_status()
            soup=BeautifulSoup(r.text,"html.parser")
        except Exception:
            return [], None
        jobs=[]
        for x in _jsonld(soup):
            title=clean_html(str(x.get("title", "")))
            if not title: continue
            company=x.get("hiringOrganization",{})
            company=company.get("name","") if isinstance(company,dict) else str(company)
            loc=x.get("jobLocation","")
            if isinstance(loc,list): loc="; ".join(str(i.get("address",i)) if isinstance(i,dict) else str(i) for i in loc)
            elif isinstance(loc,dict):
                loc=loc.get("address",loc)
                loc=loc.get("addressLocality","") if isinstance(loc,dict) else str(loc)
            apply_url=x.get("url") or x.get("sameAs") or r.url
            desc=clean_html(BeautifulSoup(str(x.get("description","")),"html.parser").get_text(" "))
            remote="remote" if re.search(r"remote|telecommut", desc+" "+str(loc), re.I) else "unknown"
            jobs.append(self._job(p,title,company,str(loc),desc,apply_url,_salary(x.get("baseSalary")),{"source_profile":p.get("name"),"category":p.get("category",""),"access_mode":p.get("access_mode","PUBLIC_HTML"),"jsonld":x},r.url,remote))
        if not jobs:
            cards=[]
            for sel in p.get("card_selectors",[]): cards.extend(soup.select(sel))
            for card in cards:
                title_node=_first(card,p.get("title_selectors",["h1","h2","h3","h4","a"]))
                title=_text(title_node)
                link_node=_first(card,p.get("link_selectors",["a[href]"]))
                href=_attr(link_node,["href"])
                if not title or not href or len(title)>220: continue
                href=urljoin(r.url,href); blob=(title+" "+_text(card)).lower()
                if p.get("title_patterns") and not any(re.search(q,title,re.I) for q in p["title_patterns"]): continue
                company=_text(_first(card,p.get("company_selectors",[]))) or p.get("default_company","")
                loc=_text(_first(card,p.get("location_selectors",[])))
                sal=_text(_first(card,p.get("salary_selectors",[])))
                remote="remote" if re.search(r"remote|work from anywhere|distributed",blob,re.I) else "unknown"
                jobs.append(self._job(p,title,company,loc,_text(card),href,sal,{"source_profile":p.get("name"),"category":p.get("category",""),"access_mode":p.get("access_mode","PUBLIC_HTML")},r.url,remote))
        if not jobs:
            pats=p.get("link_patterns",[r"/job",r"/jobs/",r"/careers/",r"/position",r"/vacanc"])
            for a in soup.select("a[href]"):
                title=_text(a); href=urljoin(r.url,_attr(a,["href"]))
                if not title or len(title)<5 or len(title)>180: continue
                if not any(re.search(q,href,re.I) for q in pats): continue
                if p.get("title_patterns") and not any(re.search(q,title,re.I) for q in p["title_patterns"]): continue
                jobs.append(self._job(p,title,p.get("default_company","") ,"",title,href,"",{"source_profile":p.get("name"),"category":p.get("category",""),"access_mode":p.get("access_mode","PUBLIC_HTML")},r.url,"unknown"))
        nxt=None
        for sel in p.get("next_selectors",['a[rel="next"]','a.next','a[aria-label*="Next"]']):
            a=soup.select_one(sel)
            if a and a.get('href'):
                nxt=urljoin(r.url,a.get('href')); break
        return jobs,nxt

    def _job(self,p,title,company,loc,desc,href,salary,raw,discovery,remote):
        company=company or p.get("default_company","") or p.get("name","")
        return Job(Job.stable_id(company,title,loc,href),title,company,loc,remote,"unknown","",desc,p.get("name",self.name),discovery,href,salary,p.get("ats","unknown"),raw)

    def _dedupe(self,jobs):
        seen=set(); out=[]
        for j in jobs:
            k=(j.title.lower(),j.company.lower(),j.apply_url.lower())
            if k in seen: continue
            seen.add(k); out.append(j)
        return out
