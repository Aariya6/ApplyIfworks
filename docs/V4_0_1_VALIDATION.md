# Remote Job Pilot v4.3.0 — Validation Gate

## What is validated in the package

The v4.3.0 package hardens the release gate around the v4 discovery and guarded-application architecture. The local validation suite currently passes **80 executed test cases**. The former browser contract cases execute against Chromium when a local Chromium executable is available.

Validated locally in the build environment:

- Chromium executable discovery
- isolated browser profile under `data/browser-profile`
- no direct `FORM_FILLED -> SUBMITTED_CONFIRMED` transition
- submission path requires `READY_TO_SUBMIT -> SUBMITTING`
- CAPTCHA/MFA remains a hard human stop
- ambiguous submit controls remain review-only
- failed forms cannot transition directly to confirmed submission
- deterministic application IDs prevent duplicate application records
- daily application cap enforcement
- source-health yield metrics exist
- application evidence and artifact hash schemas exist
- JSON-LD/source-aware discovery tests
- existing ATS/security/state/resume/application tests

## Live gates

The build environment used for packaging has no dependable external DNS. Direct HTTP attempts to representative public ATS domains fail at DNS resolution. Therefore v4.3.0 **does not falsely mark live source or live ATS validation as passed**.

Run the following on an Internet-connected machine:

```bash
python scripts/validate_release.py --live-sources
python scripts/validate_release.py --live-ats \
  --greenhouse-url "<public Greenhouse application URL>" \
  --lever-url "<public Lever application URL>" \
  --ashby-url "<public Ashby application URL>"
```

The source audit records per-source:

- jobs found
- JD availability rate
- application URL availability rate
- duplicate rate
- PASS / PARTIAL / ZERO_RESULT / FAIL

The live ATS runner is intentionally opt-in. It never submits an application; it validates navigation, form discovery, field handling and human-gate behavior.

## Chromium

For the packaged test suite, v4.3.0 can use `chromium`, `chromium-browser`, `google-chrome`, or `RJP_CHROMIUM_EXECUTABLE`. In restricted CI/container environments it uses `--no-sandbox`. The application profile remains confined to `data/browser-profile`.

## Production gate

A machine with Internet access should only be called fully validated after the live source audit and the three representative ATS checks have completed successfully.
