# Contributing

Pull requests are welcome. A few things to know before you send one:

## Setup

Follow the Installation section in `README.md`. Your real profile and company data stay in
`config/profile.json` and `config/company_universe.csv`, both gitignored — commits should never
touch them. If you need to change the *shape* of the profile schema, edit
`config/profile.example.json` instead.

## Principles this project holds to

- **No fabrication.** Nothing in this codebase invents a skill, employer, salary, or certainty it
  doesn't have. If a PR adds a feature that generates text about the user, it must read from the
  profile, not invent facts to fill a gap.
- **AI is optional, always.** Any AI-assisted feature needs a deterministic fallback that works
  with no API key configured.
- **No anti-bot evasion.** No CAPTCHA solving, stealth/fingerprint spoofing, proxy rotation for
  evasion, or login bypass. When automation can't proceed honestly, it should stop and say so
  (`REQUIRES_HUMAN` / `REQUIRES_REVIEW`), not guess.
- **Real submission is never silent.** Any change touching `apply_job` or the batch automation
  path must preserve the explicit confirmation-token requirement and the daily submission cap.

## Tests

```bash
python -m pytest
```

New source adapters, scoring logic, or automation changes should come with a test. If you're
testing something that depends on Playwright/a live site, guard it so the suite still passes in an
environment without a browser installed (see existing tests for the pattern:
`pytest.importorskip`, `RJP_CHROMIUM_EXECUTABLE` fallback).

## Adding a job source

See `config/sources.yaml` for the existing pattern. Prefer `catalog_html` with real, verified
selectors/link-patterns over a one-off adapter unless the source needs genuinely different logic
(see `app/adapters/` for existing adapters). Verify a new source actually returns jobs before
submitting — a source entry that returns zero results isn't useful to anyone.
