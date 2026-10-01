from dataclasses import dataclass, asdict
from typing import Any
import hashlib, json

@dataclass
class Job:
    id: str
    title: str
    company: str
    location: str = ""
    remote: str = "unknown"
    employment: str = "unknown"
    posted_at: str = ""
    description: str = ""
    source: str = ""
    discovery_url: str = ""
    apply_url: str = ""
    salary: str = ""
    ats: str = "unknown"
    raw: dict[str, Any] | None = None
    role_family: str = "unknown"
    fit_score: float = 0.0
    application_friction: str = "unknown"
    work_auth: str = "unknown"
    eligibility: str = "human_review"
    salary_data: dict | None = None
    canonical_url: str = ""
    country: str = ""
    country_fit: str = "unknown"
    source_category: str = ""

    def to_dict(self): return asdict(self)

    @staticmethod
    def stable_id(company, title, location, apply_url):
        key = "|".join([company.strip().lower(), title.strip().lower(), location.strip().lower(), apply_url.strip().lower()])
        return hashlib.sha256(key.encode()).hexdigest()[:20]

def json_hash(value: Any) -> str:
    raw=json.dumps(value,sort_keys=True,ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
