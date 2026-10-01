import requests,re
from bs4 import BeautifulSoup
from .base import SourceAdapter,clean_html
from ..models import Job
class PublicPage(SourceAdapter):
    name="public_page"
    def fetch(self, config):
        out=[]
        for page_url in config.get('urls',[]):
            try:
                r=requests.get(page_url,headers={'User-Agent':'RemoteJobPilot/1.0 (public job discovery)'},timeout=25); r.raise_for_status()
                soup=BeautifulSoup(r.text,'html.parser')
                for a in soup.select('a[href]'):
                    href=requests.compat.urljoin(page_url,a.get('href','')); title=clean_html(a.get_text(' '))
                    if len(title)<4 or len(title)>180: continue
                    blob=(title+' '+href).lower()
                    if not any(k in blob for k in ['job','career','vacanc','position','engineer','developer','data','product','ai','machine']): continue
                    out.append(Job(Job.stable_id(config.get('company',''),title,'',href),title,config.get('company',''),'', 'remote' if 'remote' in blob else 'unknown','unknown','', '', self.name,page_url,href,'','unknown',{}))
            except Exception as e:
                continue
        return out
