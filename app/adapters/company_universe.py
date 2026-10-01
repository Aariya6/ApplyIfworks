import csv, datetime, re, requests, yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from bs4 import BeautifulSoup
from .base import SourceAdapter, clean_html
from .ats_detect import detect_ats, extract_ats_slug
from .ats import Greenhouse, Lever, SmartRecruiters
from .ats_v3 import Ashby, Workable, Workday
from ..models import Job
from ..db import upsert_company

def _configured_ats_map():
    """Build the ATS_MAP entries for endpoint-configured providers (ashby/workable),
    skipping any whose template is not populated in config/ats_endpoints.yaml."""
    path=Path(__file__).resolve().parents[2]/'config/ats_endpoints.yaml'
    cfg=yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    out={}
    for cls in (Ashby, Workable):
        tmpl=(cfg.get(cls.name) or {}).get('endpoint_template')
        if tmpl: out[cls.name]=lambda tmpl=tmpl,cls=cls: cls(cls.name,tmpl)
    return out

ATS_MAP={'greenhouse':Greenhouse,'lever':Lever,'smartrecruiters':SmartRecruiters,'workday':Workday,**_configured_ats_map()}

class CompanyUniverse(SourceAdapter):
    name='company_universe'
    def _one(self,r):
        company=r['company'].strip(); website=r['website'].strip(); country=r.get('country','Global').strip(); sector=r.get('sector','technology')
        cid=re.sub(r'[^a-z0-9]+','-',company.lower()).strip('-') or company.lower()
        try:
            rr=requests.get(website,headers={'User-Agent':'RemoteJobPilot/4.1 public-career-discovery'},timeout=(4,10),allow_redirects=True)
            rr.raise_for_status(); soup=BeautifulSoup(rr.text,'html.parser')
            links=[]
            for a in soup.select('a[href]'):
                href=requests.compat.urljoin(rr.url,a.get('href','')); txt=clean_html(a.get_text(' '))
                if any(k in (txt+' '+href).lower() for k in ['career','jobs','join us','work with us','vacancies','open roles','careers']): links.append(href)
            careers=links[0] if links else rr.url
            ats=detect_ats(careers,rr.text); slug=extract_ats_slug(careers,ats)
            upsert_company(id=cid,name=company,domain=rr.url.split('//')[-1].split('/')[0],website=website,careers_url=careers,ats=ats,country=country,remote_policy=r.get('remote_signal',''),hiring_regions='Europe/Global' if country=='Global' else country,sector=sector,discovered_from='company_universe_v4_1',last_checked=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='DISCOVERED')
            if ats in ATS_MAP and slug:
                return ATS_MAP[ats]().discover(slug,company) if ats=='workday' else ATS_MAP[ats]().discover(slug)
            return []
        except Exception as e:
            upsert_company(id=cid,name=company,domain=website.split('//')[-1].split('/')[0],website=website,country=country,remote_policy=r.get('remote_signal',''),hiring_regions='Europe/Global' if country=='Global' else country,sector=sector,discovered_from='company_universe_v4_1',last_checked=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='ERROR',notes=str(e))
            return []
    def fetch(self,config):
        path=Path(__file__).resolve().parents[2]/config['source_file']
        rows=list(csv.DictReader(open(path,encoding='utf-8'))); out=[]
        with ThreadPoolExecutor(max_workers=min(30,len(rows))) as ex:
            futs=[ex.submit(self._one,r) for r in rows]
            for f in as_completed(futs):
                try: out.extend(f.result())
                except Exception: pass
        return out
