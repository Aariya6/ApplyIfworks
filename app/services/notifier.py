"""Desktop notifications for newly-discovered qualified/transferable jobs, so the watch loop
(app.cli's `watch` command) can actually alert the person while it runs in the background instead
of requiring them to keep checking the dashboard. winotify is optional -- if it isn't installed
(or a real Windows toast can't be raised for any reason), every notification still gets appended
to data/notifications.log so nothing is silently lost, and the loop itself never crashes because
of a missing/broken notification backend.

winotify was chosen over the more commonly-suggested win10toast after verifying live: win10toast
0.9 fails outright on a modern Python install (imports pkg_resources, which setuptools no longer
ships by default -- confirmed by actually running it here, not assumed). winotify raised a real
native Windows toast with no extra dependency.
"""
from pathlib import Path
import datetime

ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = ROOT / "data" / "notifications.log"


def notify(title, message):
    """Best-effort desktop toast; always also appended to a plain-text log so a run with no
    notification backend installed still leaves a real, inspectable record of what fired."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().isoformat()} | {title} | {message}\n")
    try:
        from winotify import Notification
        Notification(app_id="Remote Job Pilot", title=title, msg=message).show()
        return True
    except Exception:
        return False


def notify_new_jobs(new_jobs):
    """new_jobs: list of job dicts (as returned by db.jobs_created_since), already filtered to
    QUALIFIED/TRANSFERABLE tier. Silently does nothing if the list is empty -- no notification
    spam for a cycle that found nothing new."""
    if not new_jobs:
        return False
    top = new_jobs[:3]
    lines = [f"{j.get('title','?')} @ {j.get('company','?')}" for j in top]
    if len(new_jobs) > len(top):
        lines.append(f"...and {len(new_jobs) - len(top)} more")
    title = f"Remote Job Pilot: {len(new_jobs)} new qualified/transferable job{'s' if len(new_jobs)!=1 else ''}"
    return notify(title, "\n".join(lines))
