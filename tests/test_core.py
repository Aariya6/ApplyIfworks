import json, tempfile
from pathlib import Path
from app.models import Job
from app.services.tailor import factuality_check
from app.services.apply import safe_profile, ROOT

def test_stable_id_dedup():
    a=Job.stable_id('Acme','AI Engineer','Europe','https://x')
    b=Job.stable_id('Acme','AI Engineer','Europe','https://x')
    assert a==b

def test_factuality_guard():
    # Self-contained fixture profile rather than reading the real (gitignored, personal)
    # config/profile.json -- this test must pass on a fresh clone with no profile set up yet.
    p={"candidate":{"name":"Jane Doe"},"experience":[{"company":"Microsoft","title":"Intern","bullets":["Worked on Python tooling."]}],"skills":{"Languages":["Python"]}}
    ok,flags=factuality_check('Jane Doe Python Microsoft',p)
    assert ok=='PASS'
    ok,flags=factuality_check('Jane Doe Amazon OpenAI',p)
    assert ok=='REVIEW'

def test_browser_profile_is_isolated():
    p=safe_profile()
    assert (ROOT/'data').resolve() in p.resolve().parents
    assert p.name=='browser-profile'

from app.services.scoring import score_job, role_family, application_friction
from app.adapters.ats_detect import detect_ats, extract_ats_slug
from app.services.screening import classify, analyze_questions

def test_role_family_and_sales_exclusion():
    assert role_family('AI Product Manager', 'build AI product roadmaps') == 'AI_PRODUCT'
    s, reasons, fam, friction = score_job({'title':'Account Executive','description':'sales and outbound'}, {'preferences':{'exclude_titles':[],'preferred_domains':[],'regions':[]},'skills':{}})
    assert s == 0 and fam == 'EXCLUDED'

def test_ats_detection():
    assert detect_ats('https://boards.greenhouse.io/acme/jobs/1') == 'greenhouse'
    assert detect_ats('https://jobs.lever.co/acme/abc') == 'lever'
    assert extract_ats_slug('https://boards.greenhouse.io/acme/jobs/1','greenhouse') == 'acme'

def test_screening_classification():
    assert classify('Are you legally authorized to work in Germany?') == 'WORK_AUTHORIZATION'
    assert classify('What is your expected salary?') == 'SALARY'

def test_v4_catalog_source_registry():
    import yaml
    from pathlib import Path
    cfg=yaml.safe_load((Path(__file__).resolve().parents[1]/'config/sources.yaml').read_text())['sources']
    assert 'global_public_catalog' in cfg
    sites=cfg['global_public_catalog']['sites']
    names={x['name'] for x in sites}
    for required in {'Hiring.cafe','AIJobs.net','Himalayas','YC Work at a Startup','Wellfound','We Work Remotely','Jobicy','Jobgether','Landing.jobs','Relocate.me','ML Jobs','Hugging Face Jobs','Turing','Andela','Arc'}:
        assert required in names
    assert len(names) >= 50

def test_catalog_html_jsonld_extraction():
    from app.adapters.catalog_html import CatalogHTML
    html='''<html><script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"AI Engineer","description":"<p>Remote AI role</p>","hiringOrganization":{"name":"Acme"},"jobLocation":{"address":{"addressLocality":"Remote"}},"url":"https://example.com/jobs/1","baseSalary":{"currency":"EUR","value":{"minValue":60000,"maxValue":80000}}}</script></html>'''
    import requests
    class R:
        url='https://example.com/jobs'
        text=html
        def raise_for_status(self): pass
    old=requests.get
    requests.get=lambda *a,**k:R()
    try:
        jobs=CatalogHTML().fetch({'sites':[{'name':'test','url':'https://example.com/jobs'}]})
        assert len(jobs)==1 and jobs[0].title=='AI Engineer' and jobs[0].company=='Acme'
    finally:
        requests.get=old
