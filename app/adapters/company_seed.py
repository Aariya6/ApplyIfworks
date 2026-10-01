import csv, requests, re, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from pathlib import Path
from .base import SourceAdapter, clean_html
from .ats_detect import detect_ats, extract_ats_slug
from .ats import Greenhouse, Lever, SmartRecruiters
from .company_universe import ATS_MAP
from ..models import Job
from ..db import upsert_company

class CompanySeed(SourceAdapter):
    name = "company_seed"

    def _one(self, r):
        company = r["company"].strip(); website = r["website"].strip()
        try:
            rr = requests.get(website, headers={"User-Agent":"RemoteJobPilot/1.1 public-career-discovery"}, timeout=(3, 6))
            rr.raise_for_status()
            soup = BeautifulSoup(rr.text, "html.parser")
            careers = ""
            links = []
            for a in soup.select("a[href]"):
                href = requests.compat.urljoin(website, a.get("href", "")); txt = clean_html(a.get_text(" "))
                if any(k in (txt + " " + href).lower() for k in ["career", "jobs", "stellen", "vacanc", "work with us", "karriere"]):
                    links.append(href)
            if links: careers = links[0]
            ats = detect_ats(careers, rr.text); slug = extract_ats_slug(careers, ats)
            cid = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-") or company.lower()
            upsert_company(id=cid,name=company,domain=website.split('//')[-1].split('/')[0],website=website,careers_url=careers,ats=ats,city=r.get("city",""),country="Germany",remote_policy=r.get("remote_note",""),hiring_regions="Europe",sector="technology",last_checked=datetime.datetime.now(datetime.timezone.utc).isoformat(),status="DISCOVERED")
            if ats in ATS_MAP and slug:
                return ATS_MAP[ats]().discover(slug)
            if careers:
                return [Job(Job.stable_id(company,"CAREERS_PAGE",r.get("city",""),careers),"CAREERS_PAGE",company,r.get("city",""),"unknown","unknown","",r.get("remote_note",""),self.name,website,careers,"",ats,{**r,"careers_url":careers})]
            return []
        except Exception as e:
            cid = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-") or company.lower()
            upsert_company(id=cid,name=company,domain=website.split('//')[-1].split('/')[0],website=website,city=r.get("city",""),country="Germany",remote_policy=r.get("remote_note",""),discovered_from="remote-jobs-germany",last_checked=datetime.datetime.now(datetime.timezone.utc).isoformat(),status="ERROR",notes=str(e))
            return []

    def fetch(self, config):
        source = Path(__file__).resolve().parents[2] / config["source_file"]
        with open(source, encoding="utf-8") as f: rows = list(csv.DictReader(f))
        out = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(self._one, r) for r in rows]
            for f in as_completed(futures):
                try: out.extend(f.result())
                except Exception: pass
        return out
