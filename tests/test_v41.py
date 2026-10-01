import json,yaml
from pathlib import Path
from app.db import conn

def test_v41_source_registry_is_broad():
    d=yaml.safe_load(Path('config/sources.yaml').read_text())
    n=sum(len(v.get('sites',[])) for v in d['sources'].values()) + sum(1 for v in d['sources'].values() if 'sites' not in v)
    assert n >= 115
    flat=[site['name'] for v in d['sources'].values() for site in v.get('sites',[])]
    for x in ['Hiring.cafe','Himalayas','Wellfound','JobsInEnglish.dk','EnglishJobs.be','JobsFinland','Jobs.ch','No Fluff Jobs','SwedJobs','Work in Estonia','TechJobs.ie','MyCareersFuture']:
        assert x in flat

def test_v41_company_universe_is_well_formed():
    # config/company_universe.csv is personal/proprietary research data, gitignored and not part
    # of this repo -- only the small company_universe.example.csv ships publicly. This checks
    # structural validity (real header, at least a few well-formed rows), not a size threshold
    # that only this maintainer's private database would meet.
    import csv
    path='config/company_universe.csv' if Path('config/company_universe.csv').exists() else 'config/company_universe.example.csv'
    rows=list(csv.DictReader(open(path,encoding='utf-8')))
    assert len(rows) >= 5
    assert {'company','website','country','sector','remote_signal'} <= set(rows[0].keys())

def test_v41_target_countries():
    # config/profile.json is personal and gitignored -- only profile.example.json ships publicly.
    # This checks the example's own target_countries are well-formed, not specific real countries
    # that only this maintainer's private profile happens to target.
    p=json.loads(Path('config/profile.example.json').read_text())
    targets=p['preferences']['target_countries']
    assert isinstance(targets,list) and len(targets) >= 1
    assert all(isinstance(x,str) and x for x in targets)

def test_v41_country_columns_exist():
    c=conn(); cols={r[1] for r in c.execute('PRAGMA table_info(jobs)').fetchall()}; c.close()
    assert {'country','country_fit','source_category'} <= cols

def test_v41_qna_config_exists():
    d=yaml.safe_load(Path('config/qna.yaml').read_text())
    assert len(d['questions']) >= 10
    assert any(x.get('category')=='WORK_AUTHORIZATION' for x in d['questions'])


def test_v41_source_health_expands_real_sites():
    from app.services.discovery import _enabled_sources
    d=yaml.safe_load(Path('config/sources.yaml').read_text())
    enabled=_enabled_sources(d)
    names=[n for n,_ in enabled]
    assert len(names) >= 120
    assert 'Hiring.cafe' in names and 'Himalayas' in names and 'JobsInEnglish.dk' in names
    from collections import Counter
    dupes={k:v for k,v in Counter(names).items() if v>1}
    assert set(dupes) == {'Crossover','Virtual Vocations','Jobs.ch','SwissDevJobs'}
