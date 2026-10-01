import datetime
import os
from pathlib import Path

import pytest

from app.db import conn, create_application, get_application, update_application
from app.models import Job
from app.services.application_state import ALLOWED, transition
from app.services.apply import browser_launch_kwargs, safe_profile
from app.services.rate_limit import assert_can_submit


def _job(job_id="v401-test-job"):
    return Job(job_id, "AI Engineer", "Test Co", "Remote", "remote", "full-time", "", "Build AI systems", "fixture", "https://example.com/jobs", "https://example.com/jobs/1")


def test_v401_chromium_available_or_explicit_path():
    import shutil
    exe = os.getenv("RJP_CHROMIUM_EXECUTABLE") or shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    assert exe or Path.home().joinpath(".cache/ms-playwright").exists()


def test_v401_browser_profile_is_under_data():
    p = safe_profile().resolve()
    data = (Path(__file__).resolve().parents[1] / "data").resolve()
    assert data in p.parents and p.name == "browser-profile"


def test_v401_browser_launch_is_isolated_and_uses_no_sandbox_in_ci():
    kw = browser_launch_kwargs()
    assert kw["headless"] is False
    assert kw["accept_downloads"] is False
    assert "--no-sandbox" in kw["args"]


def test_v401_no_direct_submission_transition_from_form_filled():
    assert "SUBMITTED_CONFIRMED" not in ALLOWED["FORM_FILLED"]
    assert "SUBMITTING" not in ALLOWED["FORM_FILLED"]
    assert ALLOWED["READY_TO_SUBMIT"] == {"SUBMITTING", "REQUIRES_REVIEW"}


def test_v401_confirmation_state_is_terminal():
    # SUBMITTED_CONFIRMED is terminal for the *automation* funnel (no path back into
    # form-filling/submission), but it does now support human-entered outcome tracking
    # (recruiter response, interview, offer, rejection, withdrawal) -- see Phase 4's
    # application-outcome tracking, added deliberately on top of the previously-terminal state.
    assert ALLOWED["SUBMITTED_CONFIRMED"] == {"RECRUITER_RESPONSE","ASSESSMENT","INTERVIEW","FINAL","OFFER","REJECTED","WITHDRAWN"}
    for forbidden in ["READY","DRY_RUN","BROWSER_OPENED","FORM_FILLED","READY_TO_SUBMIT","SUBMITTING"]:
        assert forbidden not in ALLOWED["SUBMITTED_CONFIRMED"]


def test_v401_ambiguous_submit_requires_review():
    assert "REQUIRES_REVIEW" in ALLOWED["READY_TO_SUBMIT"]


def test_v401_failed_form_cannot_be_marked_submitted_directly():
    assert "SUBMITTED_CONFIRMED" not in ALLOWED["FAILED_FORM"]


def test_v401_duplicate_submitted_application_is_not_reopened():
    job = _job("v401-dup")
    aid = create_application(job.id)
    update_application(aid, status="SUBMITTED_CONFIRMED", submitted_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    assert get_application(aid)["status"] == "SUBMITTED_CONFIRMED"
    # The application id is deterministic per job, so a second create cannot create a second record.
    assert create_application(job.id) == aid
    c = conn(); count = c.execute("SELECT COUNT(*) FROM applications WHERE id=?", (aid,)).fetchone()[0]; c.close()
    assert count == 1


def test_v401_daily_cap_blocks_submission(monkeypatch):
    job = _job("v401-cap")
    aid = create_application(job.id)
    update_application(aid, status="SUBMITTED_CONFIRMED", submitted_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    monkeypatch.setenv("RJP_MAX_DAILY_APPLICATIONS", "1")
    with pytest.raises(RuntimeError, match="APPLICATION_LIMIT_REACHED"):
        assert_can_submit()


def test_v401_unlimited_cap_is_supported(monkeypatch):
    monkeypatch.setenv("RJP_MAX_DAILY_APPLICATIONS", "0")
    result = assert_can_submit()
    assert result["cap"] == 0 and result["remaining"] is None


def test_v401_source_health_schema_has_yield_metrics():
    c = conn()
    cols = {r[1] for r in c.execute("PRAGMA table_info(source_health)").fetchall()}
    c.close()
    assert {"jobs_found", "jd_success_rate", "application_success_rate", "duplicate_rate"} <= cols


def test_v401_application_evidence_schema_exists():
    c = conn()
    cols = {r[1] for r in c.execute("PRAGMA table_info(application_evidence)").fetchall()}
    c.close()
    assert {"application_id", "kind", "path", "value", "created_at"} <= cols


def test_v401_artifact_schema_has_hash():
    c = conn()
    cols = {r[1] for r in c.execute("PRAGMA table_info(artifacts)").fetchall()}
    c.close()
    assert "sha256" in cols


def test_v401_confirmation_detector_requires_strong_marker():
    from app.services.apply import has_submission_confirmation
    assert has_submission_confirmation("Thank you. Your application was received.") is True
    assert has_submission_confirmation("Application form") is False


def test_v401_artifact_can_be_persisted_with_sha256(tmp_path):
    import hashlib
    from app.db import create_application, save_artifact
    job = _job("v401-artifact")
    aid = create_application(job.id)
    f = tmp_path / "resume.pdf"; f.write_bytes(b"fixture-pdf")
    digest = hashlib.sha256(f.read_bytes()).hexdigest()
    save_artifact(aid, "resume_pdf", "v1", str(f), digest)
    c = conn(); row = c.execute("SELECT kind,version,path,sha256 FROM artifacts WHERE application_id=? ORDER BY id DESC LIMIT 1", (aid,)).fetchone(); c.close()
    assert tuple(row) == ("resume_pdf", "v1", str(f), digest)


def test_v401_dry_run_and_review_states_are_resumable_only_via_ready():
    # SUBMITTED_MANUAL is the one other allowed exit: the person applied themselves through the
    # official link and told the tracker so, with no automated confirmation evidence attached.
    assert ALLOWED["DRY_RUN"] == {"READY", "FAILED_FORM", "SUBMITTED_MANUAL"}
    assert ALLOWED["REQUIRES_HUMAN"] == {"READY", "FAILED_FORM", "SUBMITTED_MANUAL"}
    assert ALLOWED["REQUIRES_REVIEW"] == {"READY", "FAILED_FORM", "SUBMITTED_MANUAL"}
    assert "SUBMITTING" not in ALLOWED["REQUIRES_HUMAN"]
    assert "SUBMITTING" not in ALLOWED["REQUIRES_REVIEW"]

def test_v401_reusable_qna_fills_a_safe_labeled_field():
    from app.services.qna import seed_qna
    from app.services.apply import _fill_reusable_qna
    from pathlib import Path
    # Self-contained fixture passed explicitly to seed_qna() rather than relying on the real
    # (gitignored, personal) config/profile.json -- this test must pass deterministically on a
    # fresh clone with no profile set up yet, regardless of which profile happens to exist.
    profile={"candidate":{"email":"jane.doe@example.com"},"preferences":{},"education":[],"experience":[],"projects":[],"skills":{},"certifications":[],"hackathons":[]}
    seed_qna(profile)
    from playwright.sync_api import sync_playwright
    import os, shutil
    # Match app.services.apply.browser_launch_kwargs()'s own resolution order exactly: an
    # explicit RJP_CHROMIUM_EXECUTABLE (how this project's own .env configures Playwright's
    # bundled browser on Windows, where it's never on PATH under a bare "chromium" name) takes
    # precedence over guessing at PATH-visible binary names.
    exe=os.getenv('RJP_CHROMIUM_EXECUTABLE') or shutil.which('chromium') or shutil.which('chromium-browser') or shutil.which('google-chrome')
    assert exe
    html='<label for="email">What is your email address?</label><input id="email" name="email">'
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=exe,args=['--no-sandbox'])
        page=browser.new_page(); page.set_content(html)
        filled=_fill_reusable_qna(page,['What is your email address?'],profile)
        assert filled and page.locator('#email').input_value()==profile['candidate']['email']
        browser.close()
