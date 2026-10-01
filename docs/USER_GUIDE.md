# Remote Job Pilot v4.3.0 — User Guide

## 1. What this product does

Remote Job Pilot is a local-first job-search and guarded application assistant. It discovers public jobs and company career pages, filters them against your profile, prepares a job-specific CV and motivation letter, reuses approved screening answers, and can open/fill supported application forms in an isolated Chromium profile.

It is designed to run from VS Code. ChatGPT Pro is not required.

The system does **not** promise employment, sponsorship, India eligibility, low interview counts, or permanent availability of any company/source. Those are properties of individual live job listings.

## 2. First setup on Windows

1. Extract the ZIP.
2. Open the extracted folder in VS Code.
3. Double-click `install_windows.bat` once.
4. Let it finish installing the local virtual environment, dependencies and Chromium.
5. The installer initializes SQLite and seeds the reusable Q&A and company universe.
6. Run `start_windows.bat`.
7. Open `http://127.0.0.1:8765` in your browser.

After the first setup, use `start_windows.bat` to launch the product. You do not need ChatGPT, Codex or VS Code code edits for normal operation.

## 3. First setup on macOS/Linux

```bash
./install_unix.sh
./start_unix.sh
```

Then open `http://127.0.0.1:8765`.

## 4. Your profile

`config/profile.json` is the factual source of truth. The shipped profile contains the candidate information used for tailoring. If you deliberately need to change a personal fact, edit the profile data rather than editing the tailoring code.

The tailoring engine is prohibited from inventing employers, degrees, metrics, skills, certifications, years of experience, languages, salary claims or work-authorisation claims.

## 5. Discover jobs

From the dashboard click **Run discovery**, or use:

```bash
python -m app.cli discover
```

Then run:

```bash
python -m app.cli audit-sources
```

The audit records source status as `PASS`, `PARTIAL`, `ZERO_RESULT`, `FAIL` or `LINK_ONLY`.

Use the dashboard to review the highest-fit queue. Country and India-eligibility signals are advisory; read the actual listing before applying.

## 6. Generate a tailored application package

Open a job from the dashboard.

Click:

1. **Tailor CV**
2. **Generate letter**
3. **Run DRY RUN** when you want to inspect the browser flow without submitting.

The application directory contains:

```text
resume/vN/
  tailored_resume.pdf
  tailored_resume.docx
  tailored_resume.html
  tailoring_report.json
  metadata.json

letters/vN/
  motivation_letter.pdf
  motivation_letter.html
  motivation_letter.txt
  metadata.json
```

The PDF is the primary application artifact. SHA-256 hashes are stored so the exact version used for submission can be identified later.

## 7. Reusable screening questions

The baseline Q&A store is seeded automatically. To reseed it:

```bash
python -m app.cli seed-qna
```

Open `/qna` in the local UI to inspect and add approved answers.

Reusable factual questions such as name, email, phone, university, degree, graduation date, languages and availability can be reused. Questions involving work authorization, sponsorship, salary or ambiguous legal/demographic circumstances are intentionally not auto-approved.

## 8. Application flow

Normal flow:

```text
DISCOVERED
  ↓
SHORTLISTED / TAILORING
  ↓
READY
  ↓
BROWSER_OPENED
  ↓
FORM_ANALYZED
  ↓
FORM_FILLED
  ↓
READY_TO_SUBMIT
  ↓
SUBMITTING
  ↓
SUBMITTED_CONFIRMED
```

The browser uses only `data/browser-profile`. It never uses the normal Chrome user-data directory.

CAPTCHA, MFA, human verification, unsupported questions, ambiguous submit controls and other human-required conditions stop the workflow.

## 9. Dry run vs real application

Dry run:

```bash
python -m app.cli apply JOB_ID --dry-run
```

This opens the application, fills only supported fields, uploads the generated documents when possible, and stops before submission.

Real submission:

```bash
python -m app.cli apply JOB_ID --real-apply
```

The CLI asks for an explicit per-job confirmation token. The token is checked again immediately before the submit control is clicked.

The service layer also enforces the daily submission cap (`RJP_MAX_DAILY_APPLICATIONS`, default `30`).

## 10. What happens after Submit

A click alone does **not** mean the application is recorded as submitted.

The product looks for strong confirmation evidence such as a clear application-received/submitted marker. If it cannot establish confirmation, the application remains in a review state.

This is intentional and protects against false positives and duplicate applications.

## 11. Tracker

Open `/applications` to see:

- company
- role
- fit score
- status
- CV version
- motivation-letter version
- submitted CV hash/version
- timestamps
- artifact links

Use **Export XLSX + CSV** for external tracking.

## 12. Source coverage

The final configuration contains **128 configured source records (124 unique source names)** across global remote, European/DACH, AI/ML, startup/community, talent-network and country-specific groups, plus a **212-row company watchlist**. After deduplication during seeding, the local company table may contain fewer unique records because overlapping company names are merged.

Country groups include Denmark, Belgium, Finland, Switzerland, Poland, Sweden, Estonia, Ireland and Singapore, as well as Germany, Austria, Netherlands, France, Czechia, Norway, the UK and broader European/global sources.

Restricted sources are intentionally represented as `LINK_ONLY` where public automated extraction is not appropriate.

## 13. Optional AI enhancement

The core product works without an AI API key.

If you have an OpenAI-compatible API endpoint, configure it in `.env`:

```text
AI_API_KEY=...
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-5-mini
```

If the key is absent or the provider fails, deterministic tailoring remains available.

A ChatGPT subscription is not used by the application.

## 14. Maintenance

The main maintenance command is:

```bash
python -m app.cli discover
python -m app.cli audit-sources
```

External sites can change markup, close listings, require login or add anti-bot controls. When that happens the product records the source as degraded rather than silently treating it as healthy.

## 15. Safety boundaries

The product does not:

- bypass CAPTCHA/MFA
- bypass login walls
- spoof fingerprints
- rotate proxies to evade anti-bot systems
- use the user's normal Chrome profile
- claim a job is India-eligible when the evidence is ambiguous
- invent resume facts
- silently submit an application
- mark an unconfirmed submission as confirmed

## 16. Recommended daily workflow

```text
1. Run discovery
2. Audit source health if needed
3. Review the high-fit queue
4. Open the best matching jobs
5. Tailor CV + generate letter
6. Check the tailoring report
7. Run DRY RUN
8. Resolve any human-required questions
9. Review the completed form
10. Explicitly approve submission
11. Verify confirmation status
12. Check the tracker/export
```
