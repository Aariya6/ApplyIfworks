# Source inventory

Seeded from the supplied research and job-seeker materials.

## Remote / Europe sources

RemoteOK, ArbeitNow, Remotive, We Work Remotely, Working Nomads, Jobspresso, Himalayas, EU-remote sources, SwissDevJobs, GermanTechJobs, JointheAmbitious, and optional Google Jobs discovery through SerpAPI.

## ATS

Greenhouse, Lever, SmartRecruiters are implemented as structured adapters. The architecture is ready for Workday, Taleo, iCIMS, SuccessFactors, Personio, Teamtailor and others, but unsupported enterprise ATS are intentionally sent to manual review rather than pretending a generic adapter is reliable.

## Company discovery

The supplied `remote-jobs-germany` GitHub repository is treated as a curated company seed list. Its README is a company list rather than a complete scraping/application framework, so this product adds the missing discovery, normalization, tailoring, application and tracking layers.

## Current-source caveat

Job-board URLs, APIs, HTML structures, robots rules and ATS behavior change. Each adapter should be health-checked periodically. A failing adapter is logged and skipped rather than blocking the whole discovery run.
