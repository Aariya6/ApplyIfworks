# ATS capability matrix

The browser engine is intentionally conservative. Capability means tested behavior, not simply URL recognition.

| ATS | Detection | Discovery | Form fill | Upload | Screening | Submit | Evidence |
|---|---|---|---|---|---|---|---|
| Greenhouse | SUPPORTED | SUPPORTED via public API | PARTIAL generic | PARTIAL | PARTIAL | REVIEW | SUPPORTED |
| Lever | SUPPORTED | SUPPORTED via public API | PARTIAL generic | PARTIAL | PARTIAL | REVIEW | SUPPORTED |
| SmartRecruiters | SUPPORTED | SUPPORTED where company slug works | PARTIAL | PARTIAL | REVIEW | REVIEW | SUPPORTED |
| Ashby | SUPPORTED | adapter routing reserved | REVIEW | REVIEW | REVIEW | REVIEW | SUPPORTED |
| Workable | SUPPORTED | REVIEW | REVIEW | REVIEW | REVIEW | REVIEW | SUPPORTED |
| Personio | SUPPORTED | REVIEW | REVIEW | REVIEW | REVIEW | REVIEW | SUPPORTED |
| Teamtailor | SUPPORTED | REVIEW | REVIEW | REVIEW | REVIEW | REVIEW | SUPPORTED |
| Recruitee | SUPPORTED | REVIEW | REVIEW | REVIEW | REVIEW | REVIEW | SUPPORTED |
| Workday | SUPPORTED | REVIEW | REVIEW | REVIEW | REVIEW | REVIEW | SUPPORTED |
| iCIMS | SUPPORTED | REVIEW | REVIEW | REVIEW | REVIEW | REVIEW | SUPPORTED |
| SuccessFactors | SUPPORTED | REVIEW | REVIEW | REVIEW | REVIEW | REVIEW | SUPPORTED |
| Taleo | SUPPORTED | REVIEW | REVIEW | REVIEW | REVIEW | REVIEW | SUPPORTED |

`REVIEW` is intentional. The system must stop rather than guess when an ATS cannot be confidently handled.
