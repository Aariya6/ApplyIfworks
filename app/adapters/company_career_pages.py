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
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from .base import SourceAdapter, clean_html
from .catalog_html import CatalogHTML, _jsonld
from ..db import conn
from ..models import Job

_UA = "RemoteJobPilot/4.0 (public job discovery)"


_NON_JOB_PATH_HINTS = [
    "privacy", "how-we-hire", "our-story", "apprenticeship", "/news", "policy", "/about",
    "culture", "benefits", "faq", "/blog", "open-roles",
]


def _fetch_sitemap(url, timeout):
    """Returns (is_index, locs) or (None, []) on any failure. A sitemap index's <loc> entries
    point to OTHER sitemaps, not pages -- conflating the two was a real bug, confirmed live: it
    surfaced careers.adobe.com/sitemap1.xml and careers.adyen.com/sitemap-pt_BR.xml (more
    sitemaps, not jobs) as if they were job postings."""
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": _UA})
        if not r.ok:
            return None, []
    except Exception:
        return None, []
    is_index = "<sitemapindex" in r.text[:500].lower()
    return is_index, re.findall(r"<loc>(.*?)</loc>", r.text)


def _filter_job_paths(locs, careers_norm):
    out = []
    for l in locs:
        path = urlparse(l).path.lower()
        # Matched on the URL *path* only, not the full URL -- matching the full string let a
        # "careers." subdomain alone (with no real job path) satisfy the pattern, confirmed live.
        if not re.search(r"/job|/career|/position|/vacanc", path):
            continue
        if any(h in path for h in _NON_JOB_PATH_HINTS):
            continue
        if l.rstrip("/").lower() == careers_norm:
            continue
        if l.lower().endswith(".xml"):
            continue
        out.append(l)
    return out[:30]


def _sitemap_job_urls(careers_url, timeout):
    """When a career page itself yields nothing -- common for JS-rendered SPAs our static fetch
    can't see through -- check for a sitemap listing job URLs directly. Many sites still publish
    one for SEO even when the visible page needs JS to render a list. Follows one level of
    sitemap-index nesting, but only into a nested sitemap whose own filename suggests jobs --
    never crawls a site's entire sitemap tree."""
    origin = f"{urlparse(careers_url).scheme}://{urlparse(careers_url).netloc}"
    careers_norm = careers_url.rstrip("/").lower()
    for sitemap_path in ["/sitemap.xml", "/sitemap_index.xml"]:
        is_index, locs = _fetch_sitemap(origin + sitemap_path, timeout)
        if is_index is None:
            continue
        if is_index:
            nested = [l for l in locs if re.search(r"job|career|position|vacanc", l, re.I)][:3]
            for n in nested:
                _, sub_locs = _fetch_sitemap(n, timeout)
                result = _filter_job_paths(sub_locs, careers_norm)
                if result:
                    return result
            continue
        result = _filter_job_paths(locs, careers_norm)
        if result:
            return result
    return []


def _job_from_url(company_name, url, timeout):
    # One request, not two: this used to fetch the same URL again inside _fetch_job_detail_text
    # just to get the description, doubling latency for no reason since the title-extraction
    # fetch above already has the full page in hand.
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": _UA})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return None
    title_node = soup.select_one("h1") or soup.select_one("title")
    title = clean_html(title_node.get_text(" ")) if title_node else ""
    if not title or len(title) < 5 or len(title) > 180:
        return None
    desc = None
    for x in _jsonld(soup):
        d = clean_html(BeautifulSoup(str(x.get("description", "")), "html.parser").get_text(" "))
        if d: desc = d[:8000]; break
    if not desc:
        for sel in ["main", "article", '[class*="job"]', '[class*="description"]', '[id*="job"]']:
            node = soup.select_one(sel)
            if node:
                text = clean_html(node.get_text(" "))
                if len(text) > 200:
                    desc = text[:8000]; break
    if not desc:
        body = soup.select_one("body")
        desc = clean_html(body.get_text(" "))[:8000] if body else title
    return Job(Job.stable_id(company_name, title, "", url), title, company_name, "", "unknown", "unknown", "", desc, "company_career_pages", url, url, "", "unknown", {"via": "sitemap"})

# Generic page chrome that matches the constrained link-pattern fallback's length/href filters
# but is not a real posting -- confirmed live: a raw scrape of real career pages surfaced "Skip to
# content" and duplicate "View open roles" board links under these exact phrases.
_NAV_NOISE = {
    "careers", "jobs", "skip to content", "open positions", "view open roles", "view all roles",
    "work with us", "join us", "see all jobs", "current openings", "apply now", "home", "about",
    "about us", "contact", "contact us", "our team", "life at", "culture", "overview",
}


# A real job title either contains a recognizable role keyword, or (as with Adobe's own titles,
# which embed location/department: "Staff Product Security Engineer in New York... at Adobe")
# is long and specific. Confirmed live this is necessary: several JS-rendered career sites
# (Beekeeper, BRYTER, Backbase) returned generic site-nav text ("Products", "Resources",
# "Stories", "Cookie Policy") as "titles" for every sitemap URL, because our static fetch can't
# execute the JS that would render the real per-job content -- it just sees the same page shell
# every time. Short, keyword-less titles are exactly that failure mode, not a real posting.
_ROLE_KEYWORDS = [
    "engineer", "manager", "specialist", "analyst", "director", "lead", "associate",
    "coordinator", "developer", "designer", "intern", "officer", "representative",
    "consultant", "architect", "scientist", "researcher", "executive", "administrator",
    "recruiter", "strategist", "producer", "editor", "writer",
]


def _looks_like_real_posting(title):
    t = (title or "").strip().lower()
    if not t or t in _NAV_NOISE or len(t) < 6:
        return False
    if any(k in t for k in _ROLE_KEYWORDS):
        return True
    return len(t) >= 40  # long+specific titles (location/department suffixes) without a listed keyword


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
            jobs = [j for j in jobs if _looks_like_real_posting(j.title)]
        except Exception:
            jobs = []
        if jobs:
            return jobs
        # Nothing found on the page itself -- likely a JS-rendered listing our static fetch
        # can't see. Try the site's sitemap for job URLs directly instead of giving up.
        try:
            sitemap_urls = _sitemap_job_urls(careers_url, timeout)
            out = []; seen_desc_counts = {}
            for u in sitemap_urls:
                j = _job_from_url(company_name, u, timeout)
                if not j or not _looks_like_real_posting(j.title): continue
                # Full-text equality, not a prefix: real distinct postings legitimately share
                # boilerplate intro text ("About Adobe: Adobe is an equal opportunity
                # employer...") which made a 500-char-prefix comparison wrongly flag Adobe's
                # genuinely different postings as duplicates -- confirmed live, this cost 30 real
                # jobs. Only an exact full match means the page truly didn't render distinct
                # content.
                seen_desc_counts[j.description] = seen_desc_counts.get(j.description, 0) + 1
                out.append(j)
            return [j for j in out if seen_desc_counts.get(j.description, 0) == 1]
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
