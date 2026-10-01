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
