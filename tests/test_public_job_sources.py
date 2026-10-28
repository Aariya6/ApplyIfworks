from types import SimpleNamespace

from app.adapters.feeds import Jobicy, WeWorkRemotelyRSS
from app.adapters.router import MAP
from app.services import pipeline


def test_jobicy_public_api_normalizes_documented_fields(monkeypatch):
    payload = {
        "jobs": [
            {
                "id": 123,
                "jobTitle": "Data Analyst",
                "companyName": "Example",
                "jobGeo": "Anywhere",
                "jobType": ["Full-Time", "Remote"],
                "pubDate": "2026-10-28T15:00:00+00:00",
                "jobDescription": "<p>Analyze data</p>",
                "salaryMin": 80000,
                "salaryMax": 100000,
                "salaryCurrency": "USD",
                "salaryPeriod": "yearly",
                "url": "https://jobicy.com/jobs/123-data-analyst",
            },
            {"id": 124, "jobTitle": "", "companyName": "Missing title", "url": "https://jobicy.com/jobs/124"},
        ]
    }

    def fake_get(url, **kwargs):
        assert url == "https://jobicy.com/api/jobs?count=200"
        assert kwargs["timeout"] == 8
        return SimpleNamespace(json=lambda: payload, raise_for_status=lambda: None)

    monkeypatch.setattr("app.adapters.feeds.requests.get", fake_get)
    jobs = Jobicy().fetch({"url": "https://jobicy.com/api/jobs?count=200"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "Example"
    assert job.title == "Data Analyst"
    assert job.posted_at == "2026-10-28T15:00:00+00:00"
    assert job.apply_url == "https://jobicy.com/jobs/123-data-analyst"
    assert job.salary == "USD 80000 - 100000 yearly"
    assert pipeline.normalize_job(job, "Jobicy", "https://jobicy.com/api/jobs").posted_date_source == "pubDate"


def test_jobicy_follows_cursor_within_configured_page_cap(monkeypatch):
    seen_urls = []
    delays = []
    payloads = [
        {
            "jobs": [
                {
                    "id": 1,
                    "jobTitle": "First role",
                    "companyName": "Example",
                    "jobGeo": "Anywhere",
                    "url": "https://jobicy.com/jobs/1",
                }
            ],
            "nextCursor": "cursor with spaces",
        },
        {
            "jobs": [
                {
                    "id": 2,
                    "jobTitle": "Second role",
                    "companyName": "Example",
                    "jobGeo": "Anywhere",
                    "url": "https://jobicy.com/jobs/2",
                }
            ],
            "nextCursor": "third-page-cursor",
        },
    ]

    def fake_get(url, **kwargs):
        seen_urls.append(url)
        assert kwargs["timeout"] == 8
        payload = payloads[len(seen_urls) - 1]
        return SimpleNamespace(json=lambda: payload, raise_for_status=lambda: None)

    monkeypatch.setattr("app.adapters.feeds.requests.get", fake_get)
    monkeypatch.setattr("app.adapters.feeds.time.sleep", delays.append)
    jobs = Jobicy().fetch(
        {
            "url": "https://jobicy.com/api/jobs?count=1",
            "max_pages": 2,
            "page_delay_seconds": 0.25,
        }
    )

    assert [job.title for job in jobs] == ["First role", "Second role"]
    assert seen_urls == [
        "https://jobicy.com/api/jobs?count=1",
        "https://jobicy.com/api/jobs?count=1&cursor=cursor+with+spaces",
    ]
    assert delays == [0.25]


def test_jobicy_stops_on_repeated_cursor(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(
            json=lambda: {"jobs": [], "nextCursor": "repeat"},
            raise_for_status=lambda: None,
        )

    monkeypatch.setattr("app.adapters.feeds.requests.get", fake_get)
    monkeypatch.setattr("app.adapters.feeds.time.sleep", lambda _seconds: None)
    Jobicy().fetch({"url": "https://jobicy.com/api/jobs?count=1", "max_pages": 5})

    assert len(calls) == 2


def test_weworkremotely_rss_preserves_employer_posting_and_source_link(monkeypatch):
    xml = """<?xml version="1.0"?>
    <rss><channel><item>
      <title>Example Company: Data Engineer</title>
      <link>https://weworkremotely.com/remote-jobs/123-example-company-data-engineer</link>
      <pubDate>Wed, 28 Oct 2026 10:00:00 GMT</pubDate>
      <region>Anywhere in the World</region>
      <country></country>
      <state></state>
      <type>Full-Time</type>
      <description>&lt;p&gt;Build data systems&lt;/p&gt;</description>
    </item></channel></rss>"""

    def fake_get(url, **kwargs):
        assert url == "https://weworkremotely.com/remote-jobs.rss"
        assert kwargs["timeout"] == 8
        return SimpleNamespace(text=xml, raise_for_status=lambda: None)

    monkeypatch.setattr("app.adapters.feeds.requests.get", fake_get)
    jobs = WeWorkRemotelyRSS().fetch({"url": "https://weworkremotely.com/remote-jobs.rss"})

    assert len(jobs) == 1
    job = jobs[0]
    assert job.company == "Example Company"
    assert job.title == "Data Engineer"
    assert job.location == "Anywhere in the World"
    assert job.apply_url == "https://weworkremotely.com/remote-jobs/123-example-company-data-engineer"
    assert "Build data systems" in job.description
    assert pipeline.normalize_job(job, "We Work Remotely", "https://weworkremotely.com/remote-jobs.rss").posted_date_source == "pubDate"


def test_reviewed_sources_have_explicit_adapters_and_supported_access_methods():
    configs = pipeline._source_configs()
    registry = pipeline._load_registry(pipeline.ROOT / "config" / "pipeline_sources.csv")
    catalog_sites = {
        site["name"]: site
        for site in configs["global_public_catalog"]["sites"]
    }
    reviewed = {
        item["source_name"]: item
        for item in registry
        if item["source_name"] in {"Jobicy", "We Work Remotely"}
    }

    assert set(reviewed) == {"Jobicy", "We Work Remotely"}
    assert MAP[configs["jobicy"]["adapter"]] is Jobicy
    assert MAP[configs["we work remotely"]["adapter"]] is WeWorkRemotelyRSS
    assert reviewed["Jobicy"]["access_method"] == "official_public_api"
    assert reviewed["We Work Remotely"]["access_method"] == "public_rss"
    assert all(item["terms_reviewed"] == "true" for item in reviewed.values())
    assert catalog_sites["Jobicy"]["access_mode"] == "LINK_ONLY"
    assert catalog_sites["We Work Remotely"]["access_mode"] == "LINK_ONLY"
