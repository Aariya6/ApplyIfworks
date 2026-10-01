import time,datetime,threading,json
from pathlib import Path
from .discovery import discover, score_all

ROOT=Path(__file__).resolve().parents[2]
WATCH_STATE_PATH=ROOT/"data"/".watch_state.json"

def _now_iso(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def _load_last_checked():
    try: return json.loads(WATCH_STATE_PATH.read_text())["last_checked"]
    except Exception: return _now_iso()

def _save_last_checked(ts):
    WATCH_STATE_PATH.parent.mkdir(parents=True,exist_ok=True)
    WATCH_STATE_PATH.write_text(json.dumps({"last_checked":ts}))

def run_forever(interval_minutes=360,notify_new=False):
    """When notify_new=True (used by `python -m app.cli watch`), fires a desktop notification
    each cycle for any job discovered since the previous cycle that scored QUALIFIED or
    TRANSFERABLE -- the whole point of "launch it and let it watch while my laptop is on"."""
    interval=max(60,int(interval_minutes*60))
    if notify_new and not WATCH_STATE_PATH.exists(): _save_last_checked(_now_iso())
    while True:
        cycle_started=_now_iso()
        try: discover()
        except Exception: pass
        try: score_all()  # rescore existing jobs too, so recency/posted-age scoring stays current
        except Exception: pass
        try:
            from .company_intel import compute_all_company_fit
            from .tailor import load_profile
            compute_all_company_fit(load_profile())
        except Exception: pass
        try:
            from .skill_gap import compute_skill_gaps
            from ..db import save_skill_gap_signals
            signals,_n=compute_skill_gaps(); save_skill_gap_signals(signals)
        except Exception: pass
        if notify_new:
            try:
                from ..db import jobs_created_since
                from .notifier import notify_new_jobs
                last_checked=_load_last_checked()
                new_jobs=jobs_created_since(last_checked)
                notify_new_jobs(new_jobs)
                _save_last_checked(cycle_started)
            except Exception: pass
        time.sleep(interval)

def start_background(interval_minutes=360):
    t=threading.Thread(target=run_forever,args=(interval_minutes,),daemon=True); t.start(); return t
