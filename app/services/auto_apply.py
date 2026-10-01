"""Automate Apply: given a count, find that many genuinely-automatable (non-CAPTCHA), tailored,
not-yet-applied-to jobs, tailor + apply to each, and log exactly what happened to every one --
never a silent success/failure. This is the batch entry point behind the web UI's
"Automate Apply" control and the `app.cli auto-apply` command.

Only ATS platforms this project has a direct, tested fill/submit path for (see
ats_capabilities.py's DIRECT tier) are attempted automatically. A CAPTCHA discovered mid-flow
still stops short of auto-submitting (apply_job's batch_mode=True never blocks on input() waiting
for a human at the terminal) -- it's logged as REQUIRES_HUMAN with the form already filled, so
nothing is silently lost, but nothing is submitted without a real non-CAPTCHA confirmation either.

Duplicate protection is not bespoke to this module: create_application() uses a deterministic
per-job id, and a job already SUBMITTED_CONFIRMED/SUBMITTED_MANUAL/in any outcome state is skipped
before spending any time on it -- the same guarantee the rest of the app already relies on.
"""
from ..db import jobs, get_application
from .ats_capabilities import ATS_CAPABILITIES
from .tailor import tailor
from .apply import apply_job
from .rate_limit import assert_can_submit

# Only ATS integrations this project has a direct, tested fill/submit path for -- i.e. the
# DIRECT tier in ats_capabilities.py, never the DISCOVERY_ONLY/REVIEW tier (workday, icims,
# successfactors, taleo, teamtailor, recruitee, unknown), which this system has never proven it
# can actually fill and submit end to end.
_AUTOMATABLE_ATS = {k for k, v in ATS_CAPABILITIES.items() if v.status == "PARTIAL"}

_DONE_STATUSES = {
    "SUBMITTED_CONFIRMED", "SUBMITTED_MANUAL",
    "RECRUITER_RESPONSE", "ASSESSMENT", "INTERVIEW", "FINAL", "OFFER", "REJECTED", "WITHDRAWN",
}


def _already_applied(job_id):
    a = get_application(f"app_{job_id}")
    return bool(a and a.get("status") in _DONE_STATUSES)


def eligible_jobs(limit=200):
    """QUALIFIED/TRANSFERABLE jobs on an ATS we can actually automate, with a real apply URL,
    not already applied to. Ordered by fit_score (db.jobs() default order), so the strongest
    matches get tried first when count is smaller than the eligible pool."""
    out = []
    for j in jobs(3000):
        if j.get("fit_tier") not in {"QUALIFIED", "TRANSFERABLE"}:
            continue
        if (j.get("ats") or "").lower() not in _AUTOMATABLE_ATS:
            continue
        if not j.get("apply_url"):
            continue
        if _already_applied(j["id"]):
            continue
        out.append(j)
        if len(out) >= limit:
            break
    return out


def run_batch(count, real_apply=False):
    """Attempt up to `count` applications. In real_apply mode, generates the per-job
    CONFIRM-{job_id} token itself -- the batch call as a whole is the explicit authorization;
    per-job tokens exist to stop a single stray/scripted call, not to gate a deliberately
    requested batch run. The daily cap (RJP_MAX_DAILY_APPLICATIONS) is still enforced by
    assert_can_submit() inside apply_job on every real submission."""
    results = {
        "requested": count, "submitted": 0, "dry_run": 0, "requires_human": 0,
        "failed": 0, "cap_reached": False, "details": [],
    }
    target_field = "submitted" if real_apply else "dry_run"
    # Overshoot the candidate pool: not every attempt ends in the target_field bucket (some need
    # a human, some fail, some already got applied to between listing and attempting).
    candidates = eligible_jobs(limit=max(count * 4, count + 20))
    for job in candidates:
        if results[target_field] >= count:
            break
        job_id = job["id"]
        if _already_applied(job_id):
            continue
        if real_apply:
            try:
                assert_can_submit()
            except RuntimeError as e:
                results["cap_reached"] = True
                results["details"].append({"job_id": job_id, "title": job.get("title"), "company": job.get("company"), "status": "DAILY_CAP_REACHED", "error": str(e)})
                break
        try:
            tailor(job_id)
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"job_id": job_id, "title": job.get("title"), "company": job.get("company"), "status": "TAILOR_FAILED", "error": str(e)})
            continue
        try:
            token = f"CONFIRM-{job_id}" if real_apply else None
            r = apply_job(job_id, real_apply=real_apply, confirm_token=token, batch_mode=True)
            status = r.get("status", "UNKNOWN")
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"job_id": job_id, "title": job.get("title"), "company": job.get("company"), "status": "ERROR", "error": str(e)})
            continue
        entry = {"job_id": job_id, "title": job.get("title"), "company": job.get("company"), "status": status}
        results["details"].append(entry)
        if status == "SUBMITTED_CONFIRMED":
            results["submitted"] += 1
        elif status == "DRY_RUN":
            results["dry_run"] += 1
        elif status == "REQUIRES_HUMAN":
            results["requires_human"] += 1
        else:
            results["failed"] += 1
    results["eligible_pool_checked"] = len(candidates)
    return results
