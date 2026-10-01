import argparse
from .services.discovery import discover,score_all
from .services.tailor import tailor
from .services.letters import generate_letter
from .services.exporter import export_tracker
from .services.company_registry import seed_registry

def main():
    p=argparse.ArgumentParser(description="Remote Job Pilot - local-first job discovery and guarded application assistant")
    sub=p.add_subparsers(dest="cmd"); sub.add_parser("init"); sub.add_parser("setup"); sub.add_parser("seed-qna"); sub.add_parser("discover"); sub.add_parser("score"); sub.add_parser("audit-sources"); sub.add_parser("audit-ats"); sub.add_parser("seed-companies"); sub.add_parser("web"); sub.add_parser("export"); sub.add_parser("company-fit"); sub.add_parser("skill-gaps"); q=sub.add_parser("inspect-resume"); q.add_argument("path")
    for c in ["tailor","letter"]:
        q=sub.add_parser(c); q.add_argument("job_id")
    q=sub.add_parser("apply"); q.add_argument("job_id"); q.add_argument("--dry-run",action="store_true"); q.add_argument("--real-apply",action="store_true")
    q=sub.add_parser("daemon"); q.add_argument("--hours",type=float,default=6)
    q=sub.add_parser("watch"); q.add_argument("--minutes",type=float,default=20)
    q=sub.add_parser("auto-apply"); q.add_argument("--count",type=int,default=50); q.add_argument("--real-apply",action="store_true")
    a=p.parse_args()
    if a.cmd=="setup":
        from .services.setup import setup; print(setup())
    elif a.cmd=="seed-qna":
        from .services.qna import seed_qna; print(f"Seeded {seed_qna()} reusable answers")
    elif a.cmd=="init":
        from .db import conn; conn().close(); print("Initialized.")
    elif a.cmd=="discover": print(discover())
    elif a.cmd=="score": print(score_all()[:40])
    elif a.cmd=="seed-companies": print(f"Seeded {seed_registry()} companies")
    elif a.cmd=="company-fit":
        from .services.company_intel import compute_all_company_fit; from .services.tailor import load_profile
        print(f"Assessed {compute_all_company_fit(load_profile())} companies")
    elif a.cmd=="skill-gaps":
        from .services.skill_gap import compute_skill_gaps, recommend_project_focus
        from .db import save_skill_gap_signals
        signals,n=compute_skill_gaps(); save_skill_gap_signals(signals)
        print(f"Analyzed {n} high-fit jobs"); print(recommend_project_focus(signals))
    elif a.cmd=="audit-sources":
        from .db import source_health; print(*source_health(),sep="\n")
    elif a.cmd=="audit-ats":
        from .services.ats_capabilities import ATS_CAPABILITIES; import json; print(json.dumps({k:v.to_dict() for k,v in ATS_CAPABILITIES.items()},indent=2))
    elif a.cmd=="inspect-resume":
        from .services.resume_ingest import import_resume; print(import_resume(a.path))
    elif a.cmd=="tailor": print(tailor(a.job_id))
    elif a.cmd=="letter": print(generate_letter(a.job_id))
    elif a.cmd=="export": print(export_tracker())
    elif a.cmd=="daemon":
        from .services.scheduler import run_forever; print(f"Running discovery every {a.hours} hours"); run_forever(a.hours*60)
    elif a.cmd=="watch":
        from .services.scheduler import run_forever
        print(f"Watching for new qualified/transferable jobs every {a.minutes} minutes. Desktop notifications will fire as they're found (also logged to data/notifications.log). Leave this window running; close it to stop watching. Ctrl+C to stop.")
        run_forever(a.minutes,notify_new=True)
    elif a.cmd=="auto-apply":
        from .services.auto_apply import run_batch
        mode="REAL SUBMISSION" if a.real_apply else "DRY RUN (no real submission)"
        print(f"Automate Apply: attempting {a.count} applications [{mode}]")
        r=run_batch(a.count,real_apply=a.real_apply)
        print(f"submitted={r['submitted']} dry_run={r['dry_run']} requires_human={r['requires_human']} failed={r['failed']} cap_reached={r['cap_reached']}")
        for d in r["details"]: print(f"  {d['status']:20s} {d.get('company','?')} - {d.get('title','?')} ({d['job_id']})")
    elif a.cmd=="web":
        import uvicorn; uvicorn.run("app.main:app",host="127.0.0.1",port=8765,reload=False)
    elif a.cmd=="apply":
        from .services.apply import apply_job
        if a.real_apply:
            token=input(f"Type CONFIRM-{a.job_id} to allow final submission: "); print(apply_job(a.job_id,True,token))
        else: print(apply_job(a.job_id,False))
    else: p.print_help()
if __name__=="__main__": main()
