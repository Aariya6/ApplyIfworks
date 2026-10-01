# Remote Job Pilot

A **local-first Python** job-discovery and guarded-application assistant. It discovers remote
roles across ~90 job boards, company career pages and direct ATS integrations; scores and
classifies fit honestly (QUALIFIED / TRANSFERABLE / STRETCH / MISMATCH / EXCLUDED, never a single
opaque "match score"); tailors a real résumé and cover letter per job from your own factual
profile; and automates form-filling in a visible, guarded browser session that stops for a human
at CAPTCHAs, MFA, and any screening question it can't honestly answer.

Everything runs on your machine, against your own data. AI is optional everywhere it's used —
every AI-assisted feature has a deterministic, non-AI fallback.

## Product invariant

The system succeeds only when it can:

`DISCOVER → FETCH JD → RESOLVE OFFICIAL APPLY URL → SCORE → TAILOR FACTUALLY → VALIDATE → DRY RUN → HUMAN REVIEW → EXPLICIT SUBMIT → VERIFY EVIDENCE → TRACK EXACT CV/HASH`

It does **not** claim that every job site or ATS is fully automated, and it never fabricates a
skill, employer, metric, or certainty it doesn't have.

## Features

- **Discovery**: ~90 configured job-board/RSS/ATS sources, plus two independent company-page
  scrapers — one that queries a company's recognized ATS API directly, and a second
  (`company_career_pages`) that generically scrapes a company's own careers page when no ATS is
  recognized, closing the gap the first one leaves.
- **Scoring & fit**: an 18-family role taxonomy (AI engineering, data, product, program
  management, developer relations, music-tech, creative technology, digital humanities, and more),
  geography/work-authorization filtering, and a four-tier fit classification — never a single
  hire-probability number.
- **Company intelligence**: per-company fit tiers computed from real discovered-job data, never
  invented signal.
- **Tailoring**: per-job résumé/cover-letter generation (PDF + DOCX) from a single factual profile,
  with a deterministic fallback when no AI key is configured; immutable, versioned per application.
- **Guarded automation**: a visible Playwright browser session fills real forms, uploads the exact
  tailored résumé, and requires an explicit per-job (or per-batch) confirmation token before any
  real submission — never a silent auto-submit.
- **Automate Apply**: run a batch of N applications (dry-run or real), with a daily submission cap
  and automatic duplicate protection.
- **Cold outreach**: extracts contact emails/phones already present in a job posting's own text
  (never from LinkedIn or a third-party contact database) and drafts a cold email in your voice.
- **Daily Control Center**: a dashboard answering "did I actually apply today, and to what quality
  of job" — plus per-track (role family / country) response-rate analytics once you have enough
  real data to support them.
- **Portfolio Project Engine**: tracks real GitHub project ideas against your own skill gaps,
  computed from real job-posting requirements.

## Safety

- Never uses your normal Chrome profile — an isolated profile under `data/browser-profile/` only.
- `DRY_RUN` is the default mode everywhere.
- Real submission requires an explicit per-job confirmation token.
- CAPTCHA, MFA, work authorization, visa, salary, demographic, and ambiguous screening questions
  force `REQUIRES_HUMAN` — never guessed.
- No CAPTCHA solving, stealth/fingerprint spoofing, proxy rotation for evasion, or anti-bot
  circumvention.
- A click on Submit is not treated as a confirmed submission — the page is checked for a real
  confirmation marker first.
- A hard daily submission cap (`RJP_MAX_DAILY_APPLICATIONS`) is enforced on every real submission.

## Installation

```bash
git clone <this-repo>
cd remote-job-pilot
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

# Your personal data is gitignored and never committed -- set it up from the templates:
cp config/profile.example.json config/profile.json      # or: python -m app.cli setup
cp config/company_universe.example.csv config/company_universe.csv
cp .env.example .env

python -m app.cli init
python -m app.cli seed-qna
python -m app.cli discover
python -m app.cli web
```

For Windows, `install_windows.bat` then `start_windows.bat` automate the same steps. Open
`http://127.0.0.1:8765`.

Edit `config/profile.json` with your real information before tailoring anything — the factuality
policy at the bottom of that file is read and enforced by the tailoring engine, not just
documentation. Add real companies to `config/company_universe.csv` as you research them (the
`.example` file ships a handful of generic, well-known remote-first companies just so the project
runs out of the box).

AI is entirely optional: leave `AI_API_KEY` blank in `.env` and every feature falls back to its
deterministic path.

## Commands

```text
python -m app.cli init
python -m app.cli setup
python -m app.cli seed-qna
python -m app.cli seed-companies
python -m app.cli discover
python -m app.cli score
python -m app.cli company-fit
python -m app.cli skill-gaps
python -m app.cli audit-sources
python -m app.cli audit-ats
python -m app.cli tailor JOB_ID
python -m app.cli letter JOB_ID
python -m app.cli apply JOB_ID --dry-run
python -m app.cli apply JOB_ID --real-apply
python -m app.cli auto-apply --count 10
python -m app.cli auto-apply --count 10 --real-apply
python -m app.cli watch --minutes 20      # background watch + desktop notifications
python -m app.cli daemon --hours 6
python -m app.cli export
python -m app.cli web
python -m pytest
```

## Discovery architecture

```text
job boards / RSS feeds / public APIs
company registry (ATS-API discovery)
company career pages (generic scrape, no ATS required)
optional search API
        ↓
normalize → dedupe → JD enrichment
        ↓
role family + fit tier + remote + work-auth + country-fit + friction
        ↓
daily review queue
```

## Resume system

`config/profile.json` is the single factual source of truth. Generated résumés are immutable per
application: `data/applications/<application_id>/resume/v1/`, `v2/`, etc. Each version carries
HTML, PDF, DOCX, metadata, and a tailoring report. The exact submitted version and its SHA-256 hash
are stored independently from later versions. The tailoring engine may reorder and reframe facts,
but never invents employers, skills, degrees, metrics, certifications, salary claims, or
work-authorization claims not already in your profile.

## Application automation

The browser engine: opens the official application URL → dismisses cookie-consent dialogs that
would otherwise block every click → clicks through an initial "Apply" landing control if the real
form is gated behind one → detects CAPTCHA/MFA → waits for client-rendered forms to actually
hydrate before giving up on finding fields → maps only high-confidence canonical fields → verifies
values after filling → uploads the exact generated résumé/letter → classifies screening questions
→ stops for unsupported/legal/ambiguous questions → stops before Submit in `DRY_RUN` → requires an
explicit token in real-submission mode → requires positive confirmation evidence before marking
`SUBMITTED_CONFIRMED`.

## Testing

```bash
python -m pytest
```

The suite is local and fixture-based, with real browser-contract tests against synthetic
application fixtures. A passing suite does not mean every live job site currently works — live
source health is tracked separately via `audit-sources` and the dashboard's Sources tab.

## License

MIT — see `LICENSE`.
