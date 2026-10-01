## 4.3.0 — Final standalone release

- 120+ configured source records with country-specific boards for Denmark, Belgium, Finland, Switzerland, Poland, Sweden, Estonia, Ireland and Singapore.
- 200+ company career watchlist with direct-company discovery.
- Target-country intelligence and country-fit scoring.
- First-run setup command and reusable application Q&A store.
- Motivation letters now generated as PDF + HTML + TXT.
- Browser uploads the generated motivation-letter PDF.
- Local PDF generation uses installed Chromium when available.
- Artifact and application links exposed in the local UI.
- 80 local tests passing in the release environment.

# Changelog

## 4.0.1 — Validation hardening

- validated the complete local test suite at 75 passed; the previous 20 Playwright skips now execute against the installed Chromium binary
- added deterministic Chromium executable discovery and CI-safe launch arguments
- hardened duplicate-application prevention for already-confirmed submissions
- added final submission approval check immediately before the submit control
- added release-validation tests for daily cap, terminal submission state, ambiguous/failed submission handling, browser isolation and evidence/artifact schemas
- retained explicit CAPTCHA/MFA human-stop behavior
- added a release validation guide for live source and ATS checks


## 4.0.0
- Replaced generic public-page discovery with source-aware catalog ingestion.
- Added broad remote, European/DACH, AI/ML, startup, talent-network and specialist source registry.
- Added JSON-LD JobPosting extraction, configured source card selectors, constrained job-link parsing and per-source access modes.
- Registered restricted general boards as LINK_ONLY instead of pretending they are scrapeable.
- Added v4 source coverage documentation.


## 3.0.0 — Application Reliability Release

- Added explicit application state machine and invalid-transition protection.
- Added 20 synthetic local application fixtures and Playwright contract tests.
- Added ATS capability contracts for Greenhouse, Lever, Ashby, Workable, SmartRecruiters and Personio.
- Added configurable ATS discovery adapter framework without inventing provider endpoints.
- Added work-authorization classification and India eligibility signals.
- Added structured salary extraction and normalization.
- Added hard daily submission cap via `RJP_MAX_DAILY_APPLICATIONS` (default 30).
- Added application URL and redirect safety validation.
- Hardened browser-profile path enforcement.
- Expanded curated public job-board discovery configuration.
- Added queue visibility for work authorization and daily submission usage.
- Preserved human gates for sponsorship, salary, demographic, CAPTCHA, MFA and ambiguous screening questions.

## 1.1.0

- Discovery, source health, ATS detection, role-aware tailoring, screening classification, isolated browser workflow, evidence and tracker improvements.
