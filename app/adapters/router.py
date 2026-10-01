from concurrent.futures import ThreadPoolExecutor, as_completed
from .feeds import RemoteOK, ArbeitNow, Remotive, RSS
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

def run_source(name, cfg):
    adapter = cfg["adapter"]
    obj = MAP[adapter]()
    if adapter == "company_seed":
        return obj.fetch(cfg)
    if adapter not in {"greenhouse", "lever", "smartrecruiters", "ashby", "workable", "personio"}:
        return obj.fetch(cfg)

    companies = cfg.get("companies", [name])
    out = []
    def one(company):
        try:
            return obj.discover(company)
        except Exception:
            return []
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(companies)))) as ex:
        futures = [ex.submit(one, c) for c in companies]
        for f in as_completed(futures):
            out.extend(f.result())
    return out
