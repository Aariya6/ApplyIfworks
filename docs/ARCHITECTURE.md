# Architecture and safety invariants

## Hard invariants

1. `data/browser-profile/` is the only persistent browser profile the app may create/use.
2. No web UI field can specify a browser user-data directory.
3. No function deletes or resets Chrome profiles.
4. DRY_RUN is the default.
5. REAL_APPLY requires an exact per-job confirmation token.
6. CAPTCHA/MFA/ambiguous legal questions -> `REQUIRES_HUMAN`.
7. A submission is not marked `SUBMITTED` without confirmation evidence.
8. Resume versions are immutable.
9. AI output cannot introduce facts absent from `config/profile.json` without review.
10. Public job data only; no login/paywall/anti-bot bypass.

## Source waterfall

`public API/feed -> known ATS API -> public career-page extraction -> optional compliant search provider`

No residential proxy rotation, fingerprint spoofing, CAPTCHA solving or stealth automation is included.

## Optional AI tailoring

If `AI_API_KEY` is configured, the tailoring strategy can use the configured OpenAI-compatible chat endpoint. The model receives the structured candidate profile and job description, but its output is filtered against the master profile before it can affect the generated resume. Without a key, the deterministic role-aware strategy is used.

The LLM never becomes the source of truth for candidate facts.
