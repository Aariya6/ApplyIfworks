# Source inventory

Seeded from the supplied research and job-seeker materials.

## Remote / Europe sources

RemoteOK, ArbeitNow, Remotive, Jobicy, We Work Remotely, Working Nomads, Jobspresso, Himalayas, EU-remote sources, SwissDevJobs, GermanTechJobs, JointheAmbitious, and optional Google Jobs discovery through SerpAPI.

The pipeline currently enables only sources with a reviewed access path and a passing adapter
check. Jobicy is accessed through its public, unauthenticated Jobs API for job-discovery use; its
API requires attribution and links to Jobicy listings, which the reports retain. We Work Remotely
is accessed through its published RSS feed rather than HTML scraping; robots.txt allows the feed
path. Its terms grant limited-purpose access, so the adapter is used only for local discovery and
the application does not republish listings. Both adapters passed live checks on 2026-10-29.
Source terms and endpoints can change; re-review them before broadening usage.

## ATS

Greenhouse, Lever, SmartRecruiters are implemented as structured adapters. The architecture is ready for Workday, Taleo, iCIMS, SuccessFactors, Personio, Teamtailor and others, but unsupported enterprise ATS are intentionally sent to manual review rather than pretending a generic adapter is reliable.

## Company discovery

The supplied `remote-jobs-germany` GitHub repository is treated as a curated company seed list. Its README is a company list rather than a complete scraping/application framework, so this product adds the missing discovery, normalization, tailoring, application and tracking layers.

## Current-source caveat

Job-board URLs, APIs, HTML structures, robots rules and ATS behavior change. Each adapter should be health-checked periodically. A failing adapter is logged and skipped rather than blocking the whole discovery run.
There are 108 registry entries: eight are currently verified and 100 remain disabled for automatic
access pending review. Candidate/manual-reference URLs do not imply permission to scrape.

## Ireland and Italy references

`config/region_links.csv` contains the 251 Ireland and 251 Italy links from the supplied
country-specific snapshots. Each row is marked `manual_reference`, `terms_reviewed=false`, and
`needs_review`. Country search links may be domain-restricted searches rather than employer-hosted
filters. These links are shown in the country tabs for manual use and are not passed to scraper
adapters. Do not mark one scrape-enabled until the direct source, terms, and permitted access
method have been reviewed.
