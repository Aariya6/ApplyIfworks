# Source health and coverage

Remote Job Pilot distinguishes **configured**, **implemented**, and **verified** sources.

A source is not considered active merely because an adapter class exists. A source-health record must report search, JD extraction and official application URL success.

## Capability values

- `LIVE_API` — structured public API/JSON feed
- `ATS_DIRECT` — public ATS endpoint
- `SEARCH_API` — external search API, opt-in
- `COMPANY_REGISTRY` — company seed + career/ATS detection
- `RSS` — public feed
- `LINK_ONLY` — navigation target only; not treated as a searchable source

## Status values

- `PASS`
- `PARTIAL`
- `ZERO_RESULT`
- `JD_FAILURE`
- `APPLICATION_URL_FAILURE`
- `FAIL`

The UI exposes these values under **Sources**. The discovery pipeline does not silently convert a failed source into a working source.
