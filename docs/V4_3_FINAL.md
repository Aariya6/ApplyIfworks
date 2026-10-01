# Remote Job Pilot v4.3.0 — Final Standalone Release

This is the final standalone local baseline for operation from VS Code without ChatGPT Pro/Codex.

## Release fixes

- Source groups are flattened into per-site discovery tasks so source health is recorded per actual site rather than only per group.
- 128 configured source records are present, 124 unique source names after intentional duplicates are counted once conceptually.
- LinkedIn Jobs, Indeed and Glassdoor are explicitly `LINK_ONLY`; the system does not pretend to scrape restricted/login-gated surfaces.
- Company-career discovery no longer creates fake `CAREERS_PAGE` jobs when no public ATS is detected.
- DRY_RUN / human-review / ambiguous-review application states can be resumed without invalid state transitions.
- Reusable approved application Q&A is matched exactly or fuzzily and safe answers can be filled into compatible browser fields.
- Source-level categories are retained in stored job metadata.
- Artifact routing is constrained to the application data root.
- Windows and Unix launcher scripts remain included.

## Validation

- `pytest -q`: 80 passed, 0 failed, 0 skipped in the release environment.
- Python compilation passes.
- SQLite initialization passes.
- PDF/DOCX/HTML document generation passes.
- Browser profile isolation tests pass.

## Live-source boundary

Live source health depends on the user's Internet connection and on third-party site markup/access controls. Use:

```bash
python -m app.cli discover
python -m app.cli audit-sources
```

to establish current source-level PASS/PARTIAL/ZERO_RESULT/FAIL status.

The company watchlist is a discovery universe, not a promise of low competition, easy hiring, Indian work authorization, interview-count limits or current openings.
