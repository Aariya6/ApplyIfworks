"""Configurable ATS discovery adapters and capability contracts for v3.

No adapter invents an endpoint: each source must provide a documented public endpoint/template.
Application submission remains browser-mediated and human-gated unless an acceptance fixture proves it.
"""
import requests
from .base import ATSAdapter, clean_html
from ..models import Job
from ..services.ats_capabilities import capabilities

class ConfiguredATS(ATSAdapter):
    name='configured_ats'
    def __init__(self,name,endpoint_template): self.name=name; self.endpoint_template=endpoint_template
    def discover(self,company):
        if not self.endpoint_template: return []
        url=self.endpoint_template.format(company=company)
        r=requests.get(url,headers={'User-Agent':'RemoteJobPilot/3.0 (public job discovery)'},timeout=15); r.raise_for_status(); data=r.json()
        items=data.get('jobs',data.get('content',data if isinstance(data,list) else [])); out=[]
        for x in items:
            title=x.get('title') or x.get('text') or x.get('name') or ''
            url=x.get('absolute_url') or x.get('hostedUrl') or x.get('applyUrl') or x.get('jobAd') or x.get('url') or ''
            loc=(x.get('location') or x.get('categories') or {})
            if isinstance(loc,dict): loc=loc.get('name') or loc.get('location') or loc.get('city') or ''
            desc=clean_html(x.get('content') or x.get('descriptionPlain') or x.get('description') or x.get('body') or '')
            if title and url: out.append(Job(Job.stable_id(company,title,str(loc),url),title,company,str(loc),'unknown','unknown',x.get('createdAt') or x.get('updated_at') or '',desc,self.name,url,url,'',self.name,x))
        return out

class Ashby(ConfiguredATS):
    name='ashby'
class Workable(ConfiguredATS):
    name='workable'
class Personio(ConfiguredATS):
    name='personio'

class Workday(ATSAdapter):
    """Workday's real public job-search API, confirmed live against nvidia.wd5.myworkdayjobs.com
    and fractal.wd1.myworkdayjobs.com: POST .../wday/cxs/{tenant}/{site}/jobs for the paginated
    list, then GET .../wday/cxs/{tenant}/{site}{externalPath} per posting for the full job
    description -- the search results alone only carry a title and location, never the actual
    requirements, which is the whole point of fetching Workday postings at all. One of the most
    common enterprise ATS platforms and, until this adapter, entirely unsupported here: every
    Workday-hosted company only ever surfaced zero jobs.
    """
    name='workday'
    def discover(self, slug, display_name=None):
        try: tenant,wd,site=slug.split('|')
        except ValueError: return []
        company=display_name or tenant.replace('-',' ').title()
        base=f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
        headers={'User-Agent':'RemoteJobPilot/4.0 (public job discovery)','Content-Type':'application/json'}
        out=[]; offset=0; limit=20
        # Capped per company so a single huge enterprise board (NVIDIA: 2000+ postings) doesn't
        # dominate a discovery run -- this is a breadth-of-companies tool, not a full board mirror.
        max_jobs=60
        while len(out)<max_jobs:
            try:
                r=requests.post(f"{base}/jobs",headers=headers,json={"appliedFacets":{},"limit":limit,"offset":offset,"searchText":""},timeout=15)
                r.raise_for_status(); data=r.json()
            except Exception:
                break
            postings=data.get('jobPostings',[])
            if not postings: break
            for p in postings:
                title=p.get('title',''); path=p.get('externalPath','')
                if not title or not path: continue
                loc=p.get('locationsText','') or ''
                apply_url=f"https://{tenant}.{wd}.myworkdayjobs.com/{site}{path}"
                desc=''
                try:
                    dr=requests.get(f"{base}{path}",headers=headers,timeout=15)
                    if dr.ok:
                        info=(dr.json() or {}).get('jobPostingInfo',{})
                        desc=clean_html(info.get('jobDescription','')); loc=info.get('location') or loc
                except Exception: pass
                out.append(Job(Job.stable_id(company,title,loc,apply_url),title,company,loc,'unknown','unknown',p.get('postedOn',''),desc,self.name,apply_url,apply_url,'','workday',p))
                if len(out)>=max_jobs: break
            total=data.get('total',0); offset+=limit
            if offset>=total: break
        return out
