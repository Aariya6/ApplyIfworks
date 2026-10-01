"""Second "CareerHound"-style scraper -- but scrapes career pages themselves, not just job-board
postings. company_universe.py (the first one) only surfaces jobs for a company when it recognizes
that company's ATS (Greenhouse/Lever/SmartRecruiters/Ashby/Workable) and can extract a usable
slug; everything else gets registered as a known company with a careers_url but zero jobs, forever.

This adapter closes that gap: it re-visits every company already known to have a careers_url (via
the companies table, populated by company_seed/company_universe) and runs the same JSON-LD ->
card-selector -> constrained-link-pattern extraction CatalogHTML already uses for third-party job
boards, directly against that company's own career page. Duplicate protection is not bespoke here
-- discovery.py's find_job_identity() dedup (by company+title+location) already prevents the same
posting from being stored twice, whether it was found via ATS API or via this generic scrape.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base import SourceAdapter
from .catalog_html import CatalogHTML
from ..db import conn

# Generic page chrome that matches the constrained link-pattern fallback's length/href filters
# but is not a real posting -- confirmed live: a raw scrape of real career pages surfaced "Skip to
# content" and duplicate "View open roles" board links under these exact phrases.
_NAV_NOISE = {
    "careers", "jobs", "skip to content", "open positions", "view open roles", "view all roles",
    "work with us", "join us", "see all jobs", "current openings", "apply now", "home", "about",
    "about us", "contact", "contact us", "our team", "life at", "culture", "overview",
}


def _looks_like_real_posting(title):
    t = (title or "").strip().lower()
    return bool(t) and t not in _NAV_NOISE and len(t) >= 6


class CompanyCareerPages(SourceAdapter):
    name = "company_career_pages"

    def _one(self, engine, company_name, careers_url, timeout):
        profile = {
            "name": f"career_page:{company_name}",
            "url": careers_url,
            "category": "company_career_page_direct",
            "default_company": company_name,
            "max_pages": 1,
            "timeout": timeout,
        }
        try:
            jobs, _next_url = engine._parse_page(profile, careers_url)
            return [j for j in jobs if _looks_like_real_posting(j.title)]
        except Exception:
            return []

    def fetch(self, config):
        c = conn()
        rows = c.execute(
            "SELECT name, careers_url FROM companies WHERE careers_url IS NOT NULL AND careers_url != '' ORDER BY last_checked DESC"
        ).fetchall()
        c.close()
        max_companies = int(config.get("max_companies", 300))
        timeout = float(config.get("timeout", 15))
        targets = [(r["name"], r["careers_url"]) for r in rows[:max_companies]]
        engine = CatalogHTML()
        out = []
        with ThreadPoolExecutor(max_workers=min(20, max(1, len(targets)))) as ex:
            futures = [ex.submit(self._one, engine, name, url, timeout) for name, url in targets]
            for f in as_completed(futures):
                try:
                    out.extend(f.result())
                except Exception:
                    pass
        return engine._dedupe(out)
