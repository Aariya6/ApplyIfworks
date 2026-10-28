from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from .feeds import RemoteOK, ArbeitNow, Remotive, Jobicy, WeWorkRemotelyRSS, RSS
from .ats import Greenhouse, Lever, SmartRecruiters
from .ats_v3 import Ashby, Workable, Personio, ConfiguredATS
from .company_seed import CompanySeed
from .company_universe import CompanyUniverse
from .company_career_pages import CompanyCareerPages
from .serpapi import SerpAPI
from .public_page import PublicPage
from .catalog_html import CatalogHTML

MAP = {
    "remoteok": RemoteOK,
    "arbeitnow": ArbeitNow,
    "remotive": Remotive,
    "jobicy": Jobicy,
    "weworkremotely": WeWorkRemotelyRSS,
    "rss": RSS,
    "greenhouse": Greenhouse,
    "lever": Lever,
    "smartrecruiters": SmartRecruiters,
    "ashby": Ashby,
    "workable": Workable,
    "personio": Personio,
    "company_seed": CompanySeed,
    "company_universe": CompanyUniverse,
    "company_career_pages": CompanyCareerPages,
    "serpapi": SerpAPI,
    "public_page": PublicPage,
    "catalog_html": CatalogHTML,
}

LOGGER = logging.getLogger(__name__)
ATS_ADAPTERS = {"greenhouse", "lever", "smartrecruiters", "ashby", "workable", "personio"}


def run_source_report(name, cfg):
    adapter = cfg["adapter"]
    if adapter not in MAP:
        raise ValueError(f"Unknown source adapter: {adapter}")
    obj = MAP[adapter]()
    if adapter == "company_seed":
        return obj.fetch(cfg), []
    if adapter == "catalog_html":
        return obj.fetch_report(cfg)
    if adapter not in ATS_ADAPTERS:
        return obj.fetch(cfg), []

    companies = cfg.get("companies", [name])
    out = []
    failures = []

    def one(company):
        try:
            return company, obj.discover(company), None
        except Exception as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            error_type = f"HTTP_{status_code}" if status_code else type(exc).__name__
            LOGGER.warning("ATS source company failed: %s (%s)", company, error_type)
            return company, [], error_type

    with ThreadPoolExecutor(max_workers=min(6, max(1, len(companies)))) as ex:
        futures = [ex.submit(one, c) for c in companies]
        for f in as_completed(futures):
            company, jobs, error_type = f.result()
            out.extend(jobs)
            if error_type:
                failures.append({"company": str(company), "error_type": error_type})
    return out, failures


def run_source(name, cfg):
    jobs, _failures = run_source_report(name, cfg)
    return jobs
