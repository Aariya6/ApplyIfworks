"""Per-track (role-family / country) application performance, per Phase 4's
"experimentation rule": every career track is a hypothesis, and real response data — not a
guess — decides which ones deserve more effort. This module only aggregates what's actually in
the database. With few or zero real applications in a bucket it says so explicitly rather than
computing a misleading percentage from a tiny sample.
"""
from ..db import conn

# Applications only ever reach these states after a real submission (see application_state.py's
# ALLOWED graph: SUBMITTED_CONFIRMED/SUBMITTED_MANUAL are the only states that lead into them).
_SUBMITTED = {
    "SUBMITTED_CONFIRMED", "SUBMITTED_MANUAL",
    "RECRUITER_RESPONSE", "ASSESSMENT", "INTERVIEW", "FINAL", "OFFER", "REJECTED", "WITHDRAWN",
}
_RESPONDED = {"RECRUITER_RESPONSE", "ASSESSMENT", "INTERVIEW", "FINAL", "OFFER"}
_INTERVIEWED = {"INTERVIEW", "FINAL", "OFFER"}
_OFFERED = {"OFFER"}
_REJECTED = {"REJECTED"}

# Below this many submitted applications in a bucket, a rate is statistical noise -- report raw
# counts only, never a percentage that implies more confidence than the sample supports.
MIN_SAMPLE_FOR_RATE = 5


def _rate(numerator, denominator):
    if denominator < MIN_SAMPLE_FOR_RATE:
        return None
    return round(100 * numerator / denominator, 1)


def _aggregate(rows, key_fn):
    buckets = {}
    for r in rows:
        key = key_fn(r) or "unknown"
        b = buckets.setdefault(key, {
            "applications": 0, "submitted": 0, "responded": 0,
            "interviewed": 0, "offered": 0, "rejected": 0,
        })
        b["applications"] += 1
        status = r["status"]
        if status in _SUBMITTED:
            b["submitted"] += 1
        if status in _RESPONDED:
            b["responded"] += 1
        if status in _INTERVIEWED:
            b["interviewed"] += 1
        if status in _OFFERED:
            b["offered"] += 1
        if status in _REJECTED:
            b["rejected"] += 1
    out = []
    for key, b in buckets.items():
        out.append({
            "track": key,
            "applications": b["applications"],
            "submitted": b["submitted"],
            "responded": b["responded"],
            "interviewed": b["interviewed"],
            "offered": b["offered"],
            "rejected": b["rejected"],
            "response_rate_pct": _rate(b["responded"], b["submitted"]),
            "interview_rate_pct": _rate(b["interviewed"], b["submitted"]),
            "note": None if b["submitted"] >= MIN_SAMPLE_FOR_RATE
                else f"only {b['submitted']} submitted so far -- rate not statistically meaningful yet",
        })
    out.sort(key=lambda x: x["submitted"], reverse=True)
    return out


def _rows():
    c = conn()
    rows = c.execute(
        """SELECT applications.status AS status, jobs.role_family AS role_family, jobs.country AS country
           FROM applications JOIN jobs ON jobs.id = applications.job_id"""
    ).fetchall()
    c.close()
    return rows


def track_performance_by_role_family():
    rows = _rows()
    return _aggregate(rows, lambda r: r["role_family"])


def track_performance_by_country():
    rows = _rows()
    return _aggregate(rows, lambda r: r["country"] or "unknown")


def track_performance_summary():
    """Both breakdowns plus an honest headline: total real applications tracked so far, since
    that number gates how much confidence any of this data deserves."""
    rows = _rows()
    total_submitted = sum(1 for r in rows if r["status"] in _SUBMITTED)
    return {
        "total_applications_tracked": len(rows),
        "total_submitted": total_submitted,
        "by_role_family": _aggregate(rows, lambda r: r["role_family"]),
        "by_country": _aggregate(rows, lambda r: r["country"] or "unknown"),
        "enough_data_for_conclusions": total_submitted >= MIN_SAMPLE_FOR_RATE * 3,
    }
