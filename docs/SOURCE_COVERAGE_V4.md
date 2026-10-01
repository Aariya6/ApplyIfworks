# Remote Job Pilot v4 — Source Coverage

v4 replaces the old "generic public page" model with a **source-aware catalog adapter**. Each source has its own URL, category, access mode, link patterns and optional card selectors. Extraction prefers JSON-LD `JobPosting`, then configured source cards, then constrained job-link extraction.

## Coverage groups

### Remote/global
Hiring.cafe, AIJobs.net, Himalayas, YC Work at a Startup, We Work Remotely, Wellfound, Working Nomads, Remote Rocketship, Jobspresso, NoDesk, Remote100K, Remote.co, Jobicy, Dynamite Jobs, JustRemote, Virtual Vocations, Jobgether, Flexa Careers, 4 Day Week Jobs, Remofirst Jobs, Crossover.

### Europe / DACH
EuroRemote, EU Remote Jobs, EuropeRemotely, JointheAmbitious, Landing.jobs, Relocate.me, Welcome to the Jungle, EU-Startups Jobs, EnglishJobs.de, Berlin Startup Jobs, Vienna Startup Jobs, German Silicon Valley, Tech.eu Jobs, DevITJobs, SwissDevJobs, GermanTechJobs, Stepstone DE, Stepstone AT, Jobs.ch, Karriere.at, Arbeitsagentur, Honeypot.

### AI / ML / data / technical niches
AI Jobs, ML Jobs, Data Science Jobs, Kaggle Jobs, Hugging Face Jobs, Recooty AI Board, MLOps Community Jobs, Physical AI Jobs, Semiconductor Design Jobs, Cryptocurrency Jobs, Authentic Jobs, Built In.

### Founder / community / talent networks
Hacker News, Indie Hackers Jobs, Turing, Andela, Arc, Toptal, Contra, Gun.io, Lemon.io, Upwork, Remote.com Jobs, Deel Jobs, Oyster HR Careers, Remofirst Careers, Crossover.

### Meta/directories and specialist sources
JobBoardSearch, EuroJobs, JobsinNetwork, Europe Language Jobs, IT Jobs Worldwide, Startup.jobs, VentureLoop, Techstars, Climatebase, FlexJobs.

### General boards
Indeed, LinkedIn Jobs, Glassdoor Jobs are registered as `LINK_ONLY`. v4 does not pretend that a login-gated or restricted site is a public scraper.

## Access contract

Each source is one of:

- `LIVE_API` — existing structured API adapter.
- `ATS_DIRECT` — direct ATS adapter.
- `SOURCE_SPECIFIC_HTML` — source-aware public HTML adapter.
- `TALENT_NETWORK` — separate source class for networks/marketplaces.
- `COMPANY_REGISTRY` — company-to-career-to-ATS discovery.
- `LINK_ONLY` — surfaced in the catalog/UI, but no unauthorised scraping or login automation.

A `SOURCE_SPECIFIC_HTML` source is not considered healthy merely because its homepage loads. Source health requires jobs, a usable JD signal and an application URL signal when those are present.

## What v4 does not do

- bypass CAPTCHAs, login walls or anti-bot systems;
- scrape private APIs without permission;
- bypass paywalls;
- claim that a source is fully parsed when its public structure is unavailable;
- treat a homepage link as a job.

The system should always preserve the source's original URL and then prefer the employer/ATS application URL when it can identify one.
