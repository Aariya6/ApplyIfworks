from fastapi.testclient import TestClient

from app import main
from app.services import auto_apply, regions


def test_region_match_uses_country_and_city_aliases():
    assert regions.job_matches_region({"country": "ireland"}, "ireland")
    assert regions.job_matches_region({"location": "Dublin, Ireland"}, "ireland")
    assert regions.job_matches_region({"location": "Milano, Italia"}, "italy")
    assert not regions.job_matches_region({"location": "Belfast, Northern Ireland"}, "ireland")
    assert not regions.job_matches_region({"location": "Remote - Germany"}, "italy")


def test_remote_india_filter_requires_explicit_global_auth_signal():
    assert regions.job_remote_from_india({
        "remote": "remote",
        "work_auth": "REMOTE_WORLDWIDE",
    })
    assert regions.job_remote_from_india({
        "remote": "remote",
        "work_auth": "EOR_SUPPORTED",
    })
    assert not regions.job_remote_from_india({
        "remote": "remote",
        "work_auth": "REMOTE_EUROPE",
    })
    assert not regions.job_remote_from_india({
        "remote": "remote",
        "work_auth": "UNKNOWN",
    })


def test_supplied_region_lists_are_available_but_never_scraper_enabled():
    for country in ("ireland", "italy"):
        links = regions.load_region_links(country)
        assert len(links) == 251
        assert sum(link["category"] == "priority_employer" for link in links) == 20
        assert sum(link["category"] == "job_board" for link in links) == 30
        assert sum(link["category"] == "career_page" for link in links) == 200
        assert all(
            link["access_method"] == "manual_reference"
            and link["terms_reviewed"] == "false"
            and link["status"] == "needs_review"
            for link in links
        )
    ireland_amazon = regions.load_region_links("ireland")[0]
    italy_amazon = regions.load_region_links("italy")[0]
    assert "country=IRL" in ireland_amazon["search_url"]
    assert "loc_query=Italia" in italy_amazon["search_url"]


def test_region_page_uses_shared_job_queue_and_shows_unverified_sponsorship(monkeypatch):
    rows = [
        {
            "id": "ireland-job",
            "country": "ireland",
            "location": "Dublin, Ireland",
            "title": "Engineer",
            "company": "Example",
            "source": "fixture",
            "apply_url": "https://jobs.example.com/1",
            "work_auth": "UNKNOWN",
            "eligibility": "human_review",
            "fit_score": 91,
        },
        {
            "id": "italy-job",
            "country": "italy",
            "location": "Milano, Italia",
            "title": "Data Engineer",
            "company": "Example Italy",
            "source": "fixture",
            "apply_url": "https://jobs.example.com/2",
            "work_auth": "REMOTE_WORLDWIDE",
            "eligibility": "eligible",
            "remote": "remote",
            "fit_score": 92,
        },
    ]
    monkeypatch.setattr("app.db.jobs", lambda _limit: rows)
    with TestClient(main.app) as client:
        ireland = client.get("/ireland")
        italy = client.get("/italy?mode=remote-india")
    assert ireland.status_code == 200
    assert "Engineer" in ireland.text
    assert "Dublin, Ireland" in ireland.text
    assert "does not establish visa sponsorship" in ireland.text
    assert "Priority employers (20)" in ireland.text
    assert "Job boards (30)" in ireland.text
    assert "Employer career pages (200)" in ireland.text
    assert "Amazon / AWS — Ireland vacancies" in ireland.text
    assert "Data Engineer" not in ireland.text
    assert italy.status_code == 200
    assert "Data Engineer" in italy.text
    assert "<td>Engineer</td>" not in italy.text


def test_region_batch_uses_existing_backend_with_region_and_remote_filter(monkeypatch):
    calls = {}

    def fake_run_batch(count, **kwargs):
        calls["count"] = count
        calls.update({key: value for key, value in kwargs.items() if key != "progress_callback"})
        result = {
            "submitted": 0,
            "dry_run": count if not kwargs["real_apply"] else 0,
            "requires_human": 0,
            "failed": 0,
            "cap_reached": False,
            "eligible_pool_checked": 2,
            "details": [{"status": "DRY_RUN", "company": "Example", "title": "Engineer"}],
        }
        kwargs["progress_callback"](result, {"company": "Example", "title": "Engineer"})
        return result

    monkeypatch.setattr(auto_apply, "run_batch", fake_run_batch)
    with TestClient(main.app) as client:
        response = client.post(
            "/region/ireland/automate-apply",
            data={"count": 50, "mode": "dry_run", "filter_mode": "remote-india"},
        )
        too_many = client.post(
            "/region/italy/automate-apply",
            data={"count": 51, "mode": "dry_run", "filter_mode": "all"},
        )
    assert response.status_code == 200
    assert "DRY RUN" in response.text
    assert "Application batch results" in response.text
    assert calls == {
        "count": 50,
        "real_apply": False,
        "country": "ireland",
        "remote_from_india": True,
    }
    assert too_many.status_code == 400


def test_daily_batch_returns_results_and_rejects_invalid_requests(monkeypatch):
    calls = {}

    def fake_run_batch(count, **kwargs):
        calls["count"] = count
        calls["real_apply"] = kwargs["real_apply"]
        result = {
            "requested": count,
            "submitted": 0,
            "dry_run": count,
            "requires_human": 0,
            "failed": 0,
            "cap_reached": False,
            "eligible_pool_checked": count,
            "details": [],
        }
        kwargs["progress_callback"](result, None)
        return result

    monkeypatch.setattr(auto_apply, "run_batch", fake_run_batch)
    with TestClient(main.app) as client:
        response = client.post(
            "/daily/automate-apply",
            data={"count": 1, "mode": "dry_run"},
        )
        invalid_count = client.post(
            "/daily/automate-apply",
            data={"count": 51, "mode": "dry_run"},
        )
        invalid_mode = client.post(
            "/daily/automate-apply",
            data={"count": 1, "mode": "anything"},
        )

    assert response.status_code == 200
    assert "DRY RUN" in response.text
    assert "Dry-run prepared: 1" in response.text
    assert calls == {"count": 1, "real_apply": False}
    assert invalid_count.status_code == 400
    assert invalid_mode.status_code == 400


def test_dashboard_exposes_application_batch_separately_from_pipeline():
    form = main._application_batch_form(36)
    assert "value='36'" in form
    assert "Start application batch" in form
    assert "value='dry_run' checked" in form
    assert "value='real'" in form
    assert "The reviewed pipeline's jobs are reports-only" in main._application_batch_form(0)


def test_dashboard_renders_batch_action_and_clear_scan_label(monkeypatch):
    monkeypatch.setattr(auto_apply, "eligible_jobs", lambda limit: [{}] * 36)
    with TestClient(main.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Apply to matched jobs" in response.text
    assert "action='/daily/automate-apply'" in response.text
    assert "value='36'" in response.text
    assert "Run reviewed-source pipeline (scan only)" in response.text


def test_auto_apply_candidate_filters_restrict_country(monkeypatch):
    jobs = [
        {
            "id": "ie-1",
            "country": "ireland",
            "location": "Dublin, Ireland",
            "fit_tier": "QUALIFIED",
            "ats": "greenhouse",
            "apply_url": "https://boards.greenhouse.io/example/jobs/1",
            "work_auth": "REMOTE_WORLDWIDE",
            "remote": "remote",
        },
        {
            "id": "it-1",
            "country": "italy",
            "location": "Milano, Italia",
            "fit_tier": "QUALIFIED",
            "ats": "greenhouse",
            "apply_url": "https://boards.greenhouse.io/example/jobs/2",
            "work_auth": "REMOTE_EUROPE",
            "remote": "remote",
        },
    ]
    monkeypatch.setattr(auto_apply, "jobs", lambda _limit: jobs)
    monkeypatch.setattr(auto_apply, "_already_applied", lambda _job_id: False)
    assert {job["id"] for job in auto_apply.eligible_jobs()} == {"ie-1", "it-1"}
    assert [job["id"] for job in auto_apply.eligible_jobs(country="ireland")] == ["ie-1"]
    assert [
        job["id"]
        for job in auto_apply.eligible_jobs(country="italy", remote_from_india=True)
    ] == []
