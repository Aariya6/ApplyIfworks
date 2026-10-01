# Remote Job Pilot v3.0 — Application Reliability Release

## What v3 changes

v3 is focused on the gaps identified in the v1.1 review: real application reliability, explicit state transitions, synthetic browser acceptance fixtures, cross-border work-authorization intelligence, salary normalization, a hard submission cap, and network/browser safety enforcement.

### 1. ATS capability contracts

The project now exposes explicit capability contracts for Greenhouse, Lever, Ashby, Workable, SmartRecruiters and Personio. A detected ATS is not treated as equivalent to a proven submission flow. Submission and confirmation remain `REVIEW` until an acceptance fixture proves them.

### 2. Synthetic application suite

`tests/fixtures/applications/` contains 20 deliberately different local application forms covering ordinary fields, dynamic/hidden controls, uploads, screening questions, sponsorship questions, ambiguous submit controls, CAPTCHA/MFA markers and compensation questions. The Playwright contract test exercises each fixture without touching an external site.

### 3. Application state machine

Applications can no longer jump directly from discovery to confirmed submission. Valid transitions are enforced in `app/services/application_state.py` and logged as events.

### 4. Work authorization

Jobs are classified into signals such as `REMOTE_WORLDWIDE`, `REMOTE_EUROPE`, `EU_ONLY`, `EOR_SUPPORTED`, `CONTRACTOR_SUPPORTED`, `COUNTRY_RESTRICTED`, and `UNKNOWN`. For an India-based applicant, uncertain or locally restricted roles are kept out of the high-fit queue rather than assumed eligible.

### 5. Salary normalization

Salary strings are converted into structured currency, minimum, maximum, period and confidence fields. The raw salary text remains available.

### 6. Hard daily submission cap

`RJP_MAX_DAILY_APPLICATIONS` is enforced immediately before a real submission. The default is 30. Once the cap is reached the application is rejected with `APPLICATION_LIMIT_REACHED`.

### 7. Network safety

HTTP(S) is required for application URLs. localhost, loopback, private, link-local, reserved and multicast destinations are rejected when DNS resolution identifies them. Redirect destinations are checked again. The persistent browser profile is constrained to `data/browser-profile` and cannot be the user's normal Chrome profile.

## What v3 does not claim

- It does not claim every commercial ATS is fully automated.
- It does not solve CAPTCHA, MFA or login challenges.
- It does not bypass access controls or anti-bot systems.
- It does not infer that `Remote — Europe` means an India-based applicant has work authorization.
- It does not invent salary, visa status, experience, achievements or other candidate facts.
- External job-board adapters still require live verification on a normal network.

## Acceptance target

A v3 deployment should pass the full local unit/contract suite, then be validated against real public application pages one ATS family at a time. Only capabilities demonstrated by those tests should be promoted from `REVIEW` to `VERIFIED`.
