from pathlib import Path
import yaml
from app.services.application_state import ALLOWED

def test_v43_resume_paths_are_safe_and_submission_only_follows_ready_to_submit():
    # SUBMITTED_MANUAL is the one other allowed exit: the person applied themselves through the
    # official link and told the tracker so, with no automated confirmation evidence attached.
    assert ALLOWED['FORM_FILLED'] == {'DRY_RUN','READY_TO_SUBMIT','REQUIRES_HUMAN','REQUIRES_REVIEW'}
    assert ALLOWED['DRY_RUN'] == {'READY','FAILED_FORM','SUBMITTED_MANUAL'}
    assert ALLOWED['REQUIRES_HUMAN'] == {'READY','FAILED_FORM','SUBMITTED_MANUAL'}
    assert ALLOWED['REQUIRES_REVIEW'] == {'READY','FAILED_FORM','SUBMITTED_MANUAL'}
    assert 'SUBMITTING' not in ALLOWED['DRY_RUN']
    assert 'SUBMITTING' not in ALLOWED['REQUIRES_HUMAN']
    assert 'SUBMITTING' not in ALLOWED['REQUIRES_REVIEW']

def test_v43_restricted_sites_are_link_only():
    d=yaml.safe_load(Path('config/sources.yaml').read_text())['sources']
    names={s['name']:s for v in d.values() for s in v.get('sites',[])}
    assert names['Indeed']['access_mode']=='LINK_ONLY'
    assert names['LinkedIn Jobs']['access_mode']=='LINK_ONLY'
    assert names['Glassdoor Jobs']['access_mode']=='LINK_ONLY'

def test_v43_company_watch_pages_are_not_fake_jobs():
    src=Path('app/adapters/company_universe.py').read_text()
    assert "return [Job(Job.stable_id(company,'CAREERS_PAGE'" not in src
