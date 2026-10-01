# Remote Job Pilot v4.3.0 — Final Standalone Release

## Purpose

v4.3.0 is the final standalone baseline for local operation from VS Code. ChatGPT Pro/Codex is not required to run discovery, scoring, resume tailoring, PDF generation, motivation letters, reusable application Q&A, tracking, source health, or guarded browser assistance.

Optional AI enhancement remains available through an OpenAI-compatible API key. The core product has a deterministic fallback and does not depend on a ChatGPT subscription.

## Coverage

- 120 configured source records in `config/sources.yaml`.
- 212 company-career watchlist records in `config/company_universe.csv`.
- Country targeting for Denmark, Belgium, Finland, Switzerland, Poland, Sweden, Estonia, Ireland, Singapore plus wider Europe/UK.
- Remote/global, European/DACH, AI/ML, startup/community, talent-network and country-specific sources.
- Restricted/login-gated sources are explicitly marked `LINK_ONLY` rather than falsely treated as scrapers.

## Candidate application pipeline

`DISCOVER → COUNTRY/WORK-AUTH FILTER → CURATE → TAILOR → RESUME PDF/DOCX → MOTIVATION LETTER PDF/HTML/TXT → REUSABLE Q&A → GUARDED BROWSER → READ-BACK → HUMAN APPROVAL → SUBMIT → CONFIRMATION EVIDENCE → TRACK`

## Documents

Every tailored application can retain:

- ATS-oriented resume HTML
- Resume PDF
- Resume DOCX
- Tailoring report
- Motivation letter PDF
- Motivation letter HTML/TXT
- metadata and SHA-256 hashes

The exact artifact used for submission is recorded against the application.

## Screening answers

`config/qna.yaml` contains the baseline reusable question set. `python -m app.cli seed-qna` loads approved factual answers into SQLite. The browser assistant can reuse exact approved answers. Work authorization, visa, salary, demographic and ambiguous questions remain human-gated.

## Company discovery

The company universe is a **watchlist/discovery universe**, not a claim that every company is currently hiring or accepts candidates from India. The adapter visits public company sites, looks for career/job links, detects supported ATS platforms where possible, and records the company even when no live job can be extracted.

## Application safety

- Browser profile is confined to `data/browser-profile`.
- The user's normal Chrome profile is not accepted.
- CAPTCHA/MFA/human verification causes a hard stop.
- FORM_FILLED cannot directly transition to submission.
- REAL_APPLY requires an explicit per-job confirmation token.
- Daily submission cap is enforced at the service layer.
- Duplicate confirmed applications are prevented.
- A submit click without strong confirmation evidence remains review-required.
- No CAPTCHA solving, stealth, proxy rotation for evasion, login bypass or anti-bot circumvention.

## External-site limitation

No job platform can be guaranteed permanently stable. Sites can change markup, require login, add anti-bot controls, close roles or change geographic eligibility. The product records source health as PASS/PARTIAL/ZERO_RESULT/FAIL/LINK_ONLY and preserves the official application URL when available.

Run on an Internet-connected machine:

```bash
python -m app.cli discover
python -m app.cli audit-sources
```

For non-submitting ATS smoke tests:

```bash
python scripts/validate_release.py --live-ats \
  --greenhouse-url "<public Greenhouse application URL>" \
  --lever-url "<public Lever application URL>" \
  --ashby-url "<public Ashby application URL>"
```

## Local release validation

The packaged release was validated with:

```text
80 passed
0 failed
0 skipped
```

The release environment had a usable Chromium executable. Live external source/ATS validation remains intentionally user-run because it depends on Internet access and current third-party pages.
