# Remote Job Pilot v4.0 — Source Expansion Release

v4 keeps the v3 application-reliability architecture and fixes the largest remaining discovery gap: the system no longer treats a handful of generic public pages as if they represented the remote-job market.

## Source coverage

The v4 registry contains **92 configured source records** across:

- remote/global boards
- Europe/DACH boards
- AI/ML/data specialist boards
- startup and founder communities
- talent networks / marketplaces
- specialist and meta directories
- direct company career discovery

The source registry is generated into `config/source_catalog.yaml` and operational configuration lives in `config/sources.yaml`.

## Ingestion

`catalog_html` is source-aware rather than the v3 `public_page` link scanner. For each configured source it can:

1. fetch the source page with bounded timeout;
2. follow a small number of explicit pagination links;
3. extract schema.org `JobPosting` JSON-LD first;
4. fall back to configured card selectors;
5. fall back to constrained job-link patterns;
6. preserve source/discovery/application URLs;
7. infer remote signal and retain raw source metadata;
8. feed the normal v3 dedupe, scoring, work-authorization and salary pipeline.

## Important honesty boundary

Some sites are registered as `LINK_ONLY` because public automated access is restricted, login-gated, or otherwise not safely available to this local application. They remain visible in the source universe, but v4 does not pretend to scrape them.

That includes general/restricted surfaces such as LinkedIn, Indeed and Glassdoor, plus individual talent platforms where public job ingestion is not reliably available.

## Existing v3 controls retained

- explicit application state machine
- hard daily application cap
- browser-profile isolation
- CAPTCHA/MFA human gates
- SSRF protections
- salary normalization
- India work-authorization signals
- ATS capability contracts
- immutable resume evidence
- synthetic application fixtures

## Verification

The build environment has no dependable external DNS, so v4 does not claim that every live source returned jobs during packaging. Run:

```bash
python -m app.cli discover
python -m app.cli audit-sources
```

from a normal Internet-connected machine. Source health records distinguish failures, zero-result sources and partial results instead of converting network failures into fake success.
