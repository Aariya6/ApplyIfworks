# Security model

## Browser isolation

Automation uses only `data/browser-profile/`. The application has no UI parameter that accepts a normal Chrome user-data directory.

## Network safety

Future network fetchers must reject localhost, loopback, link-local/cloud metadata addresses, private RFC1918 ranges, `file://`, and other non-public targets when a URL originates from untrusted job content.

## Credentials

Secrets belong in `.env` or the user's OS secret store. Never write API keys, passwords, OTPs, cookies or session tokens into SQLite, screenshots, exported spreadsheets or logs.

## Evidence

Screenshots are application-scoped. CAPTCHA/MFA/password/OTP states stop the workflow and are not programmatically bypassed.

## Resume integrity

The exact submitted resume version and SHA-256 hash are stored separately from the current resume version.
