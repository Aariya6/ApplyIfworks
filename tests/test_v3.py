import os,pytest
from pathlib import Path
from app.services.job_intelligence import extract_salary,work_auth,eligibility_for_india
from app.services.application_state import ALLOWED
from app.services.ats_capabilities import capabilities
from app.services.security import validate_application_url

def test_salary_range_and_currency():
    x=extract_salary('Compensation: €50k–€70k per year')
    assert x.currency=='EUR' and x.minimum==50000 and x.maximum==70000 and x.period=='annual'

def test_work_auth_worldwide(): assert work_auth('Remote worldwide; contractors welcome')=='REMOTE_WORLDWIDE'
def test_work_auth_eu_only(): assert eligibility_for_india(work_auth('EU citizens only'))=='probably_ineligible_without_local_work_rights'
def test_unknown_is_human_review(): assert eligibility_for_india('UNKNOWN')=='human_review'
def test_ats_contracts():
    for name in ['greenhouse','lever','ashby','workable','smartrecruiters','personio']:
        c=capabilities(name); assert all(k in c for k in ['discover','jd','application_url','fill_fields','uploads','screening','human_gate','evidence'])
def test_state_machine_has_no_direct_submission_from_discovered(): assert 'SUBMITTED_CONFIRMED' not in ALLOWED['DISCOVERED']
def test_state_machine_submission_requires_submitting(): assert ALLOWED['READY_TO_SUBMIT']=={'SUBMITTING','REQUIRES_REVIEW'}
def test_security_blocks_localhost():
    with pytest.raises(ValueError): validate_application_url('http://localhost:8000/apply')
def test_security_blocks_loopback_ip():
    with pytest.raises(ValueError): validate_application_url('http://127.0.0.1/apply')

def test_security_requires_http():
    with pytest.raises(ValueError): validate_application_url('file:///tmp/apply.html')

@pytest.mark.parametrize('n',range(1,21))
def test_synthetic_application_fixture_exists(n):
    assert (Path(__file__).parent/'fixtures'/'applications'/f'case_{n:02d}.html').exists()

def _ms_playwright_cache_dir():
    # ~/.cache/ms-playwright is the Linux/macOS location; Playwright installs to
    # %LOCALAPPDATA%\ms-playwright on Windows instead, so checking only the former made this
    # fallback silently useless on Windows (the actual failure mode this fixture hit).
    localappdata=os.getenv('LOCALAPPDATA')
    if localappdata and Path(localappdata,'ms-playwright').exists(): return True
    return Path.home().joinpath('.cache/ms-playwright').exists()

@pytest.fixture(scope='module')
def browser_contract_context():
    pytest.importorskip('playwright.sync_api')
    from playwright.sync_api import sync_playwright
    import shutil
    # Match app.services.apply.browser_launch_kwargs()'s own resolution order: an explicit
    # RJP_CHROMIUM_EXECUTABLE (how this project's .env configures Playwright's bundled browser on
    # Windows, where it's never on PATH under a bare "chromium" name) takes precedence.
    executable=os.getenv('RJP_CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('chromium-browser') or shutil.which('google-chrome')
    if not executable and not _ms_playwright_cache_dir(): pytest.skip('Playwright browser binary not installed in this environment')
    pw=sync_playwright().start()
    try:
        try:
            browser=pw.chromium.launch(headless=True, executable_path=executable, args=['--no-sandbox'] if executable else None)
        except Exception as exc:
            pw.stop(); pytest.skip(f'Playwright Chromium binary unavailable: {exc}')
        yield browser
        browser.close()
    finally:
        try: pw.stop()
        except Exception: pass

@pytest.mark.parametrize('n',range(1,21))
def test_synthetic_application_browser_contract(n,browser_contract_context):
    html=(Path(__file__).parent/'fixtures'/'applications'/f'case_{n:02d}.html').read_text()
    page=browser_contract_context.new_page(); page.set_content(html)
    assert page.locator('form').count()==1
    assert page.locator('input,textarea,select').count()>=6
    page.close()
