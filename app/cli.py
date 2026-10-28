import argparse
from .services.discovery import discover,score_all
from .services.tailor import tailor
from .services.letters import generate_letter
from .services.exporter import export_tracker
from .services.company_registry import seed_registry

def main():
    p=argparse.ArgumentParser(description="Remote Job Pilot - local-first job discovery and guarded application assistant")
    sub=p.add_subparsers(dest="cmd"); sub.add_parser("init"); sub.add_parser("setup"); sub.add_parser("seed-qna"); sub.add_parser("discover",help="Run legacy discovery into the dashboard queue; use run for the reviewed pipeline"); sub.add_parser("score"); sub.add_parser("audit-sources"); sub.add_parser("audit-ats"); sub.add_parser("seed-companies"); sub.add_parser("web"); sub.add_parser("export"); sub.add_parser("company-fit"); sub.add_parser("skill-gaps"); q=sub.add_parser("inspect-resume"); q.add_argument("path")
    q=sub.add_parser("run",help="Run the reviewed-source job intelligence pipeline (never submits applications)")
    q.add_argument("--config",default="config/pipeline.yaml"); q.add_argument("--since-hours",type=float); q.add_argument("--min-score",type=float); q.add_argument("--priority-score",type=float); q.add_argument("--max-sources",type=int); q.add_argument("--max-jobs",type=int); q.add_argument("--concurrency",type=int); q.add_argument("--refresh-source"); q.add_argument("--export",dest="export_dir"); q.add_argument("--dry-run",action="store_true",default=True)
    q=sub.add_parser("source-test",help="Test one source only when its terms are marked reviewed")
    q.add_argument("source_name")
    sub.add_parser("pipeline-health",help="Show the local pipeline adapter health report")
    q=sub.add_parser("pipeline-tracker",help="List or update the local human-reviewed pipeline tracker")
    q.add_argument("--status")
    q.add_argument("--update-job")
    q.add_argument("--set-status")
    q.add_argument("--applied-at")
    q.add_argument("--follow-up-date")
    q.add_argument("--outcome")
    for c in ["tailor","letter"]:
        q=sub.add_parser(c); q.add_argument("job_id")
    q=sub.add_parser("apply"); q.add_argument("job_id"); q.add_argument("--dry-run",action="store_true"); q.add_argument("--real-apply",action="store_true")
    q=sub.add_parser("daemon"); q.add_argument("--hours",type=float,default=6)
    q=sub.add_parser("watch"); q.add_argument("--minutes",type=float,default=20)
    q=sub.add_parser("auto-apply"); q.add_argument("--count",type=int,default=50); q.add_argument("--real-apply",action="store_true")
    a=p.parse_args()
    if a.cmd=="run":
        from pathlib import Path
        import yaml
        from .services.pipeline import run_pipeline
        config_path=Path(a.config)
        config=yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        defaults=config.get("pipeline",{})
        result=run_pipeline(
            since_hours=a.since_hours if a.since_hours is not None else float(defaults.get("since_hours",24)),
            min_score=a.min_score if a.min_score is not None else float(defaults.get("min_score",90)),
            priority_score=a.priority_score if a.priority_score is not None else float(defaults.get("priority_score",95)),
            max_sources=a.max_sources if a.max_sources is not None else defaults.get("max_sources"),
            max_jobs=a.max_jobs if a.max_jobs is not None else defaults.get("max_jobs"),
            concurrency=a.concurrency if a.concurrency is not None else int(defaults.get("concurrency",1)),
            requests_per_second=float(defaults.get("requests_per_second",1)),
            refresh_source=a.refresh_source,
            dry_run=a.dry_run,
            export_dir=Path(a.export_dir) if a.export_dir else Path(config.get("export_dir","data/exports")),
            registry_path=Path(config.get("source_registry","config/pipeline_sources.csv")),
            profile_path=Path(config.get("profile","config/profile.json")),
        )
        print("Job pipeline summary (dry run; no applications submitted):")
        for key,value in result.items():
            print(f"{key}: {value}")
    elif a.cmd=="source-test":
        from .services.pipeline import test_source
        print(test_source(a.source_name))
    elif a.cmd=="pipeline-health":
        from .services.pipeline import pipeline_health
        rows=pipeline_health()
        if not rows: print("No pipeline source checks recorded.")
        for row in rows: print(row)
    elif a.cmd=="pipeline-tracker":
        import json
        from .services.pipeline import pipeline_tracker, update_pipeline_tracker
        changes=[a.set_status,a.applied_at,a.follow_up_date,a.outcome]
        if a.update_job:
            if not any(value is not None for value in changes):
                p.error("pipeline-tracker --update-job requires at least one update field")
            update_pipeline_tracker(
                a.update_job,
                status=a.set_status,
                applied_at=a.applied_at,
                follow_up_date=a.follow_up_date,
                outcome=a.outcome,
            )
            print(f"Updated tracker record for {a.update_job}")
        elif any(value is not None for value in changes):
            p.error("pipeline-tracker update fields require --update-job")
        else:
            print(json.dumps(pipeline_tracker(a.status),indent=2,ensure_ascii=False))
    elif a.cmd=="setup":
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
