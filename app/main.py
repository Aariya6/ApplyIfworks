from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse,RedirectResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json,html
from .db import jobs,applications,get_job,source_health,companies,qnas,save_qna
from .services.tailor import tailor,load_profile
from .services.letters import generate_letter
from .services.exporter import export_tracker
from .services.resume_ingest import import_resume
from .services.rate_limit import daily_cap,submitted_today
from .services.job_intelligence import eligibility_for_india
from .services.paste_sheet import build_and_save_paste_sheet, load_saved_paste_sheet
from .services.apply import mark_applied_manual
from .db import create_application, get_application, update_application
from .db import portfolio_projects, get_portfolio_project, skill_gap_signals
from .services.skill_gap import compute_skill_gaps, recommend_project_focus
from .services.company_intel import compute_all_company_fit
from .services.scoring import days_since_posted
from .services.jd_intelligence import extract_requirements, requirement_gap_report, application_state_signal, hard_constraint_preflight
from .db import applications_for_company
from .services.regions import REGIONS, load_region_links, region_jobs

SOURCE_CHANNELS = ["application", "referral", "recruiter_search", "direct_outreach", "event", "portfolio", "open_source", "other"]
REJECTION_REASONS = ["unspecified", "no_response", "role_filled", "experience_gap", "location_or_work_auth",
    "salary_mismatch", "lost_to_other_candidate", "process_stalled", "other"]
ROOT=Path(__file__).resolve().parents[1]; app=FastAPI(title="Remote Job Pilot",version="4.3.0"); app.mount("/static",StaticFiles(directory=str(ROOT/"app/static")),name="static")
def page(title,body): return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title>"
    f"<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
    f"<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300..700;1,9..144,400..600&family=Work+Sans:wght@400;500;600;700&display=swap'>"
    f"<link rel='stylesheet' href='/static/app.css'><script defer src='/static/sort.js'></script></head><body>"
    f"<nav><div class='brand'>Remote Job Pilot</div><div class='nav-links'><a href='/'>Dashboard</a><a href='/pipeline'>Pipeline</a><a href='/ireland'>Ireland</a><a href='/italy'>Italy</a><a href='/sources'>Sources</a><a href='/companies'>Companies</a><a href='/skill-gaps'>Skill Gaps</a><a href='/portfolio'>Portfolio</a><a href='/profile'>Profile</a><a href='/daily'>Daily</a><a href='/applications'>Tracker</a><a href='/resume'>Resume</a><a href='/qna'>Application Q&amp;A</a><a href='/settings'>Safety</a></div></nav>"
    f"<main>{body}</main></body></html>")
@app.get("/",response_class=HTMLResponse)
def home(tier: str = "ALL"):
    p=load_profile(); js=jobs(2000)
    tier_counts={"QUALIFIED":0,"TRANSFERABLE":0,"STRETCH":0,"MISMATCH":0,"EXCLUDED":0}
    for j in js: tier_counts[j.get("fit_tier") or "MISMATCH"]=tier_counts.get(j.get("fit_tier") or "MISMATCH",0)+1
    pool=[j for j in js if (j.get("fit_tier") or "MISMATCH") not in {"MISMATCH","EXCLUDED"}]
    if tier!="ALL": pool=[j for j in pool if j.get("fit_tier")==tier]
    ready=sorted(pool,key=lambda j:j.get("fit_score",0),reverse=True)[:60]
    sh=source_health(); apps=applications(500); needs=sum(1 for a in apps if a.get("status") in {"REQUIRES_HUMAN","READY_TO_SUBMIT","SUBMIT_CLICKED_REVIEW"})
    tier_badge={"QUALIFIED":"🟢 Qualified","TRANSFERABLE":"🔵 Transferable","STRETCH":"🟡 Stretch","MISMATCH":"⚪ Mismatch","EXCLUDED":"⛔ Excluded"}
    tabs="".join(f"<a href='/?tier={t}'{' style=\"font-weight:bold\"' if tier==t else ''}>{tier_badge.get(t,t)} ({tier_counts.get(t,0)})</a> " for t in ["ALL","QUALIFIED","TRANSFERABLE","STRETCH"])
    def posted_cell(j):
        age=days_since_posted(j.get('posted_at'))
        if age is None: return 99999,"—"
        if age<=0: return 0,"today"
        if age==1: return 1,"1d ago"
        return age,f"{age}d ago"
    cards="".join((lambda age_val,age_txt: f"<tr><td><b>{j.get('fit_score',0):.0f}</b><br><small>{tier_badge.get(j.get('fit_tier'),'')}</small></td><td><b>{html.escape(j['title'])}</b><br>{html.escape(j['company'])}</td><td>{html.escape(j['location'])}<br><small>{html.escape(j.get('country',''))}</small></td><td>{html.escape(j.get('role_family',''))}</td><td>{html.escape(j.get('application_friction',''))}</td><td data-val='{html.escape(j.get('work_auth','UNKNOWN'))}'>{html.escape(j.get('work_auth','unknown'))}</td><td data-val='{age_val}'>{age_txt}</td><td><a href='/job/{j['id']}'>Open</a></td></tr>")(*posted_cell(j)) for j in ready)
    body=f"<div class='hero'><h1>EU Remote Job Queue</h1><p>This legacy queue uses previously discovered jobs. Run the reviewed-source pipeline for a fresh, auditable search and see its results on the Pipeline page.</p><form method='post' action='/pipeline/run'><button>Run reviewed-source pipeline</button></form></div><div class='stats'><div><b>{len(js)}</b><span>legacy jobs stored</span></div><div><b>{len(ready)}</b><span>shown</span></div><div><b>{len(apps)}</b><span>applications</span></div><div><b>{needs}</b><span>needs attention</span></div><div><b>{len(sh)}</b><span>legacy source records</span></div><div><b>{submitted_today()}/{daily_cap() or '∞'}</b><span>daily submissions</span></div></div><h2>Legacy queue</h2><p>{tabs}</p><table class='sortable'><tr><th>Fit</th><th>Role</th><th>Location / Country</th><th>Family</th><th>Friction</th><th data-sort='text'>Work auth</th><th data-sort='num'>Date posted</th><th></th></tr>{cards}</table>"; return page("Dashboard",body)
@app.post("/discover")
def discover_route(): return run_reviewed_pipeline()

def run_reviewed_pipeline():
    import yaml
    from .services.pipeline import run_pipeline

    config_path=ROOT/"config/pipeline.yaml"
    config=yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    defaults=config.get("pipeline",{})
    result=run_pipeline(
        since_hours=float(defaults.get("since_hours",24)),
        min_score=float(defaults.get("min_score",90)),
        priority_score=float(defaults.get("priority_score",95)),
        max_sources=defaults.get("max_sources"),
        max_jobs=defaults.get("max_jobs"),
        concurrency=int(defaults.get("concurrency",1)),
        requests_per_second=float(defaults.get("requests_per_second",1)),
        dry_run=True,
        registry_path=ROOT/config.get("source_registry","config/pipeline_sources.csv"),
        profile_path=ROOT/config.get("profile","config/profile.json"),
        export_dir=ROOT/config.get("export_dir","data/exports"),
    )
    return RedirectResponse(f"/pipeline?run_id={result['run_id']}",303)

@app.post("/pipeline/run")
def pipeline_run_route(): return run_reviewed_pipeline()

@app.get("/sources",response_class=HTMLResponse)
def sources():
    from .services.pipeline import pipeline_overview
    data=pipeline_overview()
    rows=[]
    for source in data["sources"]:
        health=source.get("health") or {}
        status=health.get("status") or source.get("status","needs_review")
        checked=health.get("checked_at") or source.get("last_checked_at") or "not checked"
        count=health.get("jobs_found","—")
        error=health.get("error_type") or ""
        rows.append(
            "<tr>"
            f"<td>{html.escape(source.get('source_name',''))}</td>"
            f"<td>{html.escape(source.get('source_type',''))}</td>"
            f"<td>{html.escape(source.get('access_method',''))}</td>"
            f"<td>{html.escape(source.get('terms_reviewed','false'))}</td>"
            f"<td>{html.escape(status)}</td><td>{html.escape(str(count))}</td>"
            f"<td>{html.escape(str(checked))}</td><td>{html.escape(str(error))}</td>"
            "</tr>"
        )
    body=(
        "<h1>Source Registry and Health</h1>"
        "<p>Only sources marked verified with reviewed terms are queried by the pipeline. "
        "Candidate/manual-import links remain review-only and are not scraped.</p>"
        "<form method='post' action='/pipeline/run'><button>Run approved pipeline sources</button></form>"
        "<p><a href='/pipeline'>View latest pipeline results →</a></p>"
        "<table><tr><th>Source</th><th>Type</th><th>Access</th><th>Terms reviewed</th>"
        "<th>Last check status</th><th>Jobs</th><th>Last checked</th><th>Error/status detail</th></tr>"
        + "".join(rows)
        + "</table>"
    )
    return page("Sources",body)

@app.get("/pipeline",response_class=HTMLResponse)
def pipeline_page():
    from .services.pipeline import canonicalize_url, pipeline_overview
    data=pipeline_overview()
    run=data["run"]
    if not run:
        run_section="<p>No pipeline run recorded yet. Run the reviewed-source pipeline to check the six currently verified sources.</p>"
        jobs_section="<p>No jobs to display until a pipeline run completes.</p>"
    else:
        summary=data["summary"]
        metrics=[
            ("Run ID",run["id"]),("Started",run["started_at"]),("Completed",run["completed_at"] or "in progress"),
            ("Sources selected",summary.get("sources_selected",0)),("Successful",summary.get("sources_succeeded",0)),
            ("Partial",summary.get("sources_partial",0)),("Failed",summary.get("sources_failed",0)),
            ("Jobs discovered",summary.get("discovered",0)),("Duplicates removed",summary.get("deduplicated",0)),
            ("Stale",summary.get("stale",0)),("Ineligible",summary.get("ineligible",0)),
            ("Unknown eligibility",summary.get("unknown_eligibility",0)),("Drafts generated",summary.get("documents_generated",0)),
            ("Errors",summary.get("errors",0)),
        ]
        run_rows="".join(
            f"<tr><th>{html.escape(str(label))}</th><td>{html.escape(str(value))}</td></tr>"
            for label,value in metrics
        )
        run_section=f"<table>{run_rows}</table>"
        rendered=[]
        for assessment in data["assessments"]:
            job=assessment["job"]
            original=canonicalize_url(job.get("source_url",""))
            apply=canonicalize_url(job.get("application_url",""))
            links=[]
            if original:
                links.append(f"<a href='{html.escape(original,quote=True)}' target='_blank' rel='noopener noreferrer'>listing</a>")
            if apply:
                links.append(f"<a href='{html.escape(apply,quote=True)}' target='_blank' rel='noopener noreferrer'>apply</a>")
            reasons=assessment.get("hard_exclusions",[])+assessment.get("verification_reasons",[])
            rendered.append(
                "<tr>"
                f"<td>{html.escape(assessment.get('tier',''))}</td>"
                f"<td>{float(assessment.get('score',0)):.2f}</td>"
                f"<td>{html.escape(job.get('employer',''))}</td>"
                f"<td>{html.escape(job.get('title',''))}</td>"
                f"<td>{html.escape(assessment.get('eligibility',''))}</td>"
                f"<td>{html.escape(job.get('posted_at') or 'unknown')}</td>"
                f"<td>{html.escape(job.get('source_name',''))}</td>"
                f"<td>{' · '.join(links)}</td>"
                f"<td>{html.escape('; '.join(reasons))}</td>"
                "</tr>"
            )
        jobs_section=(
            "<p>Showing up to 100 highest-scoring records from the latest run. A listing is not "
            "an approval to apply; review eligibility and every draft yourself.</p>"
            "<table><tr><th>Tier</th><th>Score</th><th>Employer</th><th>Role</th><th>Eligibility</th>"
            "<th>Posted</th><th>Source</th><th>Links</th><th>Reason / verification needed</th></tr>"
            + "".join(rendered)
            + "</table>"
        )
    body=(
        "<h1>Reviewed-source job pipeline</h1>"
        "<p>This pipeline uses only reviewed, verified public sources. It creates reports and "
        "human-review drafts; it does not submit applications. Existing legacy jobs remain in "
        "the separate dashboard queue.</p>"
        "<form method='post' action='/pipeline/run'><button>Run pipeline now (dry run)</button></form>"
        f"<p>Command line: <code>python -m app.cli run --config config/pipeline.yaml --since-hours 24 --min-score 90 --dry-run</code></p>"
        f"{run_section}<h2>Latest job assessments</h2>{jobs_section}"
        "<p>Exports: <code>data/exports/&lt;run-id&gt;.json</code>, "
        "<code>.csv</code>, <code>.xlsx</code>, and <code>.html</code>.</p>"
    )
    return page("Reviewed-source pipeline",body)

def _region_page(region: str, mode: str = "all"):
    from .db import jobs

    region_key = region.casefold()
    if region_key not in REGIONS:
        return HTMLResponse("Unknown country tab", status_code=404)
    if mode not in {"all", "remote-india"}:
        return HTMLResponse("Unknown country filter", status_code=400)
    config = REGIONS[region_key]
    matches = region_jobs(jobs(3000), region_key, mode)
    reference_links = load_region_links(region_key)
    rows = []
    for job in matches[:100]:
        auth = html.escape(str(job.get("work_auth") or "unknown"))
        eligibility = html.escape(str(job.get("eligibility") or "human review required"))
        location = html.escape(str(job.get("location") or "unknown"))
        title = html.escape(str(job.get("title") or ""))
        company = html.escape(str(job.get("company") or ""))
        source = html.escape(str(job.get("source") or ""))
        apply_url = str(job.get("apply_url") or "")
        apply_link = (
            f"<a href='{html.escape(apply_url, quote=True)}' target='_blank' rel='noopener noreferrer'>official route</a>"
            if apply_url.startswith("https://")
            else "no verified HTTPS route"
        )
        rows.append(
            "<tr>"
            f"<td>{float(job.get('fit_score') or 0):.0f}</td>"
            f"<td>{title}</td><td>{company}</td><td>{location}</td>"
            f"<td>{source}</td><td>{auth}<br>{eligibility}</td>"
            f"<td>{apply_link}</td>"
            f"<td><a href='/job/{html.escape(str(job.get('id') or ''), quote=True)}'>review</a></td>"
            "</tr>"
        )
    if rows:
        listings = (
            "<table><tr><th>Fit</th><th>Role</th><th>Employer</th><th>Location</th>"
            "<th>Source</th><th>Work authorization signal</th><th>Application</th><th></th></tr>"
            + "".join(rows)
            + "</table>"
        )
        if len(matches) > 100:
            listings = f"<p>Showing 100 of {len(matches)} matches.</p>" + listings
    else:
        listings = (
            "<p>No matching jobs are currently stored in the shared application queue. "
            "A country tab is a filter, not evidence that a source was scraped or that a vacancy exists.</p>"
        )
    mode_links = (
        f"<a href='/{region_key}?mode=all'>All roles in {config['label']}</a> · "
        f"<a href='/{region_key}?mode=remote-india'>Explicitly India-compatible remote roles</a>"
    )
    link_groups = []
    category_labels = {
        "country_search": "Country-specific starting link",
        "priority_employer": "Priority employers",
        "job_board": "Job boards",
        "career_page": "Employer career pages",
    }
    for category, label in category_labels.items():
        group = [link for link in reference_links if link["category"] == category]
        if not group:
            continue
        items = "".join(
            "<li>"
            f"<strong>{html.escape(link['source_name'])}</strong>: "
            f"<a href='{html.escape(link['search_url'], quote=True)}' target='_blank' rel='noopener noreferrer'>country search</a> · "
            f"<a href='{html.escape(link['career_url'], quote=True)}' target='_blank' rel='noopener noreferrer'>career/source page</a>"
            "</li>"
            for link in group
        )
        link_groups.append(
            f"<details><summary>{html.escape(label)} ({len(group)})</summary><ul>{items}</ul></details>"
        )
    body = (
        f"<h1>{html.escape(config['label'])} jobs</h1>"
        "<p>These are country/location filters over the shared legacy job and application queue. "
        "The reviewed pipeline remains available on <a href='/pipeline'>Pipeline</a>; its separate "
        "records are not silently treated as application-ready jobs.</p>"
        f"<p>{mode_links}</p>"
        "<p>Remote-in-country does not mean work is allowed from India. The remote filter requires "
        "an existing worldwide/contractor/EOR signal, but still does not establish visa sponsorship. "
        "Verify work authorization, relocation, language, and the vacancy itself before applying.</p>"
        "<h2>Country-specific career and board links</h2>"
        "<p>These 251 links per country came from the supplied lists. They are manual references, "
        "not verified vacancies or scraped sources. They are not contacted by the scraper until "
        "access and terms are reviewed.</p>"
        + "".join(link_groups)
        + f"<h2>Stored jobs ({len(matches)})</h2>{listings}"
        "<h2>Run the shared application backend</h2>"
        "<p>Batch attempts are restricted to jobs in this country tab that already meet the existing "
        "qualified/transferable and supported-ATS gates. Maximum 50 per run. Real submission is "
        "separately selected; CAPTCHA, MFA, uncertain eligibility, and ambiguous screening questions "
        "still stop for human review.</p>"
        f"<form method='post' action='/region/{region_key}/automate-apply'>"
        "<label>Maximum jobs: <input type='number' name='count' min='1' max='50' value='10' required></label> "
        "<label><input type='radio' name='mode' value='dry_run' checked> Dry run only</label> "
        "<label><input type='radio' name='mode' value='real'> Real submission</label> "
        f"<input type='hidden' name='filter_mode' value='{mode}'>"
        "<button>Run batch</button></form>"
        "<p>The Daily page's all-country batch can include Ireland and Italy candidates from this "
        "shared queue when they meet the same gates. The reviewed-source pipeline itself only prepares "
        "reports and never submits applications.</p>"
    )
    return page(f"{config['label']} jobs", body)


@app.get("/ireland", response_class=HTMLResponse)
def ireland_page(mode: str = "all"):
    return _region_page("ireland", mode)


@app.get("/italy", response_class=HTMLResponse)
def italy_page(mode: str = "all"):
    return _region_page("italy", mode)


@app.post("/region/{region}/automate-apply", response_class=HTMLResponse)
def region_automate_apply_route(
    region: str,
    count: int = Form(...),
    mode: str = Form(...),
    filter_mode: str = Form("all"),
):
    region_key = region.casefold()
    if region_key not in REGIONS:
        return HTMLResponse("Unknown country tab", status_code=404)
    if count < 1 or count > 50:
        return HTMLResponse("Batch size must be from 1 to 50.", status_code=400)
    if mode not in {"dry_run", "real"}:
        return HTMLResponse("Choose dry_run or real mode.", status_code=400)
    if filter_mode not in {"all", "remote-india"}:
        return HTMLResponse("Unknown country filter.", status_code=400)
    from .services.auto_apply import run_batch

    result = run_batch(
        count,
        real_apply=(mode == "real"),
        country=region_key,
        remote_from_india=(filter_mode == "remote-india"),
    )
    details = "".join(
        f"<tr><td>{html.escape(str(item.get('status','')))}</td>"
        f"<td>{html.escape(str(item.get('company') or ''))}</td>"
        f"<td>{html.escape(str(item.get('title') or ''))}</td></tr>"
        for item in result["details"]
    ) or "<tr><td colspan='3'>No jobs qualified for an attempt.</td></tr>"
    summary = (
        f"<h1>{html.escape(REGIONS[region_key]['label'])} batch result</h1>"
        f"<p>Requested {count}; mode: {'real submission' if mode == 'real' else 'dry run'}; "
        f"submitted {result['submitted']}; dry-run {result['dry_run']}; "
        f"human review {result['requires_human']}; failed {result['failed']}.</p>"
        f"<p>Eligible jobs checked: {result['eligible_pool_checked']}."
        f"{' Daily cap reached.' if result['cap_reached'] else ''}</p>"
        f"<table><tr><th>Status</th><th>Employer</th><th>Role</th></tr>{details}</table>"
        f"<p><a href='/{region_key}?mode={filter_mode}'>Back to {html.escape(REGIONS[region_key]['label'])}</a></p>"
    )
    return page("Country batch result", summary)


@app.post('/audit-sources')
def audit_sources_route():
    return run_reviewed_pipeline()

_target_badge={"PRIMARY_TARGET":"🎯 Primary target","SECONDARY_TARGET":"🔹 Secondary target","NOT_CURRENTLY_ACTIONABLE":"— not actionable"}
_TIER_ORDER={"PRIMARY_TARGET":0,"SECONDARY_TARGET":1,"NOT_CURRENTLY_ACTIONABLE":2}
def _company_fit(r):
    try: return json.loads(r.get("company_fit_detail") or "null")
    except Exception: return None

@app.get("/companies",response_class=HTMLResponse)
def company_page(view: str = "targets"):
    rows=companies(5000)
    enriched=[(r,_company_fit(r)) for r in rows]
    needs_research_count=sum(1 for r,_ in enriched if r.get("status")=="NEEDS_MANUAL_RESEARCH")
    if view=="targets":
        enriched=[(r,f) for r,f in enriched if f and f["target_tier"] in {"PRIMARY_TARGET","SECONDARY_TARGET"}]
        enriched.sort(key=lambda rf: (_TIER_ORDER.get(rf[1]["target_tier"],9), -rf[1]["qualified_roles"]))
    elif view=="needs_research":
        enriched=[(r,f) for r,f in enriched if r.get("status")=="NEEDS_MANUAL_RESEARCH"]
        enriched.sort(key=lambda rf: (rf[0]["name"] or "").lower())
    else:
        enriched.sort(key=lambda rf: (rf[0]["name"] or "").lower())
    def _tab(v,label):
        return f"<a href='/companies?view={v}'{' style=\"font-weight:bold\"' if view==v else ''}>{label}</a>"
    tabs=(_tab("targets","Targets only")+" &nbsp; "+_tab("needs_research",f"Needs manual research ({needs_research_count})")
        +" &nbsp; "+_tab("all",f"All {len(rows)} companies"))
    def _row(r,f):
        if f:
            badge=_target_badge.get(f["target_tier"],f["target_tier"])
            roles=f"{f['qualified_roles']}Q / {f['transferable_roles']}T / {f['stretch_roles']}S"
            india=f["remote_from_india"]
        else:
            badge="not yet assessed"; roles="—"; india="UNKNOWN"
        return f"<tr><td><a href='/company/{r['id']}'>{html.escape(r['name'])}</a></td><td>{html.escape(badge)}</td><td>{html.escape(roles)}</td><td>{html.escape(india)}</td><td>{html.escape(r.get('ats','unknown'))}</td><td><a href='{html.escape(r.get('careers_url') or r.get('website',''))}' target='_blank'>careers ↗</a></td></tr>"
    body=f"<h1>Company Registry</h1><p>{tabs}</p><p><small>Q = qualified roles, T = transferable, S = stretch. \"Remote from India\" is aggregated honestly from each company's open-role eligibility data — UNKNOWN means no posting said either way, not that it's disallowed.</small></p><table><tr><th>Company</th><th>Target status</th><th>Matching roles</th><th>Remote from India</th><th>ATS</th><th></th></tr>"+"".join(_row(r,f) for r,f in enriched)+"</table>"; return page("Companies",body)

@app.get("/company/{company_id}",response_class=HTMLResponse)
def company_detail(company_id):
    from .db import get_company
    co=get_company(company_id)
    if not co: return page("Not found","<h2>Company not found</h2>")
    niche_fields=["niche_domain","geography_strategy","personal_fit","ownership_potential",
        "india_eligibility_note","target_role_families_note","why_target_note"]
    niche_html=""
    if any(co.get(k) for k in niche_fields):
        niche_rows="".join(f"<tr><td>{html.escape(k.replace('_',' ').title())}</td><td>{html.escape(str(co.get(k) or ''))}</td></tr>" for k in niche_fields)
        niche_html=f"<h2>Target-list research notes</h2><table>{niche_rows}</table>"
        if co.get("status")=="NEEDS_MANUAL_RESEARCH":
            search_link=f"<a href='{html.escape(co.get('reference_search_url') or '')}' target='_blank'>Google search →</a>" if co.get("reference_search_url") else ""
            niche_html+=f"<p class='warning'><b>No confirmed career-page URL</b> — not auto-crawled. {search_link}</p>"
    # FP10 company relationship ledger: every application ever tied to this company, so the
    # relationship is visible as a whole rather than as isolated, disconnected records.
    ledger=applications_for_company(co["name"])
    if ledger:
        ledger_rows="".join(f"<tr><td><a href='/job/{r['job_id']}'>{html.escape(r.get('title',''))}</a></td><td>{html.escape(r['status'])}</td>"
            f"<td>{html.escape(r.get('source_channel') or '—')}</td><td>{html.escape(r.get('submitted_at') or '—')}</td>"
            f"<td>{html.escape(r.get('rejection_reason') or '—')}</td><td>{html.escape(r.get('updated_at',''))}</td></tr>" for r in ledger)
        ledger_html=f"<h2>Application history with this company</h2><table><tr><th>Role</th><th>Status</th><th>Channel</th><th>Submitted</th><th>Rejection reason</th><th>Updated</th></tr>{ledger_rows}</table>"
    else:
        ledger_html="<h2>Application history with this company</h2><p><small>No applications recorded with this company yet.</small></p>"
    f=_company_fit(co)
    if not f:
        body=f"<h1>{html.escape(co['name'])}</h1><p>{html.escape(co.get('country',''))} · <a href='{html.escape(co.get('careers_url') or co.get('website',''))}' target='_blank'>careers page ↗</a></p>{niche_html}<p><small>Not yet assessed for job-fit — run company-fit computation (recompute-fit route, or the CLI).</small></p>{ledger_html}"
        return page(co["name"],body)
    tier_html="".join(f"<tr><td>{html.escape(k.replace('_',' ').title())}</td><td><b>{html.escape(str(v))}</b></td></tr>" for k,v in f.items() if k not in {"why_targeted","relevant_job_ids"})
    why_html="".join(f"<li>{html.escape(w)}</li>" for w in f.get("why_targeted",[]))
    role_jobs=[get_job(jid) for jid in f.get("relevant_job_ids",[])]; role_jobs=[j for j in role_jobs if j]
    tier_badge={"QUALIFIED":"🟢","TRANSFERABLE":"🔵","STRETCH":"🟡"}
    roles_html="".join(f"<tr><td>{tier_badge.get(j.get('fit_tier'),'')} {html.escape(j.get('fit_tier',''))}</td><td><a href='/job/{j['id']}'>{html.escape(j['title'])}</a></td><td>{j.get('fit_score',0):.0f}</td></tr>" for j in sorted(role_jobs,key=lambda j:j.get('fit_score',0),reverse=True))
    body=f"<h1>{html.escape(co['name'])}</h1><p>{html.escape(_target_badge.get(f['target_tier'],f['target_tier']))} · {html.escape(co.get('country',''))} · <a href='{html.escape(co.get('careers_url') or co.get('website',''))}' target='_blank'>careers page ↗</a></p>{niche_html}<h2>Company fit</h2><table>{tier_html}</table><p><b>Why targeted:</b></p><ul>{why_html}</ul><h2>Matching open roles</h2><table><tr><th>Tier</th><th>Role</th><th>Fit</th></tr>{roles_html}</table>{ledger_html}"; return page(co["name"],body)

@app.post("/companies/recompute-fit")
def recompute_company_fit():
    n=compute_all_company_fit(load_profile()); return RedirectResponse(f"/companies?view=targets",303)

def _refresh_skill_gaps():
    from .db import save_skill_gap_signals
    signals,_n=compute_skill_gaps(); save_skill_gap_signals(signals); return skill_gap_signals()

@app.get("/skill-gaps",response_class=HTMLResponse)
def skill_gaps_page():
    signals=skill_gap_signals()
    if not signals: signals=_refresh_skill_gaps()
    recommendation=recommend_project_focus([{**s,"example_job_ids":json.loads(s["example_job_ids"])} for s in signals])
    def _skill_row(s):
        ex_links=" ".join(f"<a href='/job/{jid}'>job</a>" for jid in json.loads(s["example_job_ids"]))
        return f"<tr><td><b>{html.escape(s['skill'])}</b></td><td>{s['job_count']}</td><td>{ex_links}</td></tr>"
    rows="".join(_skill_row(s) for s in signals)
    projects=portfolio_projects()
    proj_links="".join(f"<li><a href='/portfolio/{p['id']}'>{html.escape(p['name'])}</a> — {html.escape(p['status'])}</li>" for p in projects)
    body=f"<h1>Skill-Gap Analysis</h1><p>Computed from every job you're actually a credible fit for (QUALIFIED/TRANSFERABLE/STRETCH), checking for named technologies that recur but aren't yet in your profile. Not a keyword-frequency guess — a curated technology taxonomy, word-boundary matched.</p><form method='post' action='/skill-gaps/recompute'><button>Recompute now</button></form><h2>Recurring gaps</h2><table><tr><th>Skill</th><th>Job count</th><th>Examples</th></tr>{rows}</table><h2>Recommendation</h2><p>{html.escape(recommendation)}</p><h2>Portfolio projects</h2><ul>{proj_links}</ul>"; return page("Skill Gaps",body)

@app.post("/skill-gaps/recompute")
def skill_gaps_recompute():
    _refresh_skill_gaps(); return RedirectResponse("/skill-gaps",303)

@app.get("/portfolio",response_class=HTMLResponse)
def portfolio_list():
    from .services.project_priority import rank_projects
    ranked=rank_projects()
    top=ranked[0] if ranked else None
    top_html=""
    if top:
        reasons_html="".join(f"<li>{html.escape(r)}</li>" for r in top["reasons"])
        top_html=(f"<div class='hero'><h2>Recommended next build (evidence-based, not a hire-probability): {html.escape(top['project']['name'])} — score {top['score']}</h2>"
            f"<ul>{reasons_html}</ul><p><small>Score is \"portfolio-evidence value\", not a promise of interviews or jobs.</small></p></div>")
    rows="".join(f"<tr><td><a href='/portfolio/{p['id']}'>{html.escape(p['name'])}</a></td><td>{html.escape(p['status'])}</td><td>{p.get('priority_score',0):.1f}</td><td>{html.escape(p.get('build_status') or 'NOT_STARTED')}</td><td>{html.escape(p.get('target_job_family') or '')}</td></tr>" for p in sorted(portfolio_projects(),key=lambda p:-(p.get('priority_score') or 0)))
    body=f"<h1>Portfolio Project Engine</h1><p>Projects selected and specced to close real, evidence-backed skill gaps found in <a href='/skill-gaps'>Skill-Gap Analysis</a> — not a random project list.</p>{top_html}<table><tr><th>Project</th><th>Status</th><th>Priority score</th><th>Build status</th><th>Target job family</th></tr>{rows}</table>"; return page("Portfolio",body)

@app.get("/portfolio/{project_id}",response_class=HTMLResponse)
def portfolio_detail(project_id):
    import json as _json
    p=get_portfolio_project(project_id)
    if not p: return page("Not found","<h2>Project not found</h2>")
    from .services.portfolio_evidence import compute_project_job_evidence
    evidence=compute_project_job_evidence(p)
    lifecycle=["IDEA","SPECIFIED","BUILDING","LOCAL_COMPLETE","TESTED","DEPLOYED","GITHUB_READY","PUBLISHED"]
    cur=p["status"] if p["status"] in lifecycle else "IDEA"
    lifecycle_html="".join(f"<b>[{html.escape(s)}]</b>" if s==cur else html.escape(s) for s in lifecycle)
    status_fields=["build_status","test_status","deployment_status","documentation_status","screenshot_status","readme_status","github_status"]
    status_html="".join(f"<tr><td>{html.escape(f.replace('_',' ').title())}</td><td>{html.escape(p.get(f) or 'NOT_STARTED')}</td></tr>" for f in status_fields)
    reasons=_json.loads(p.get("priority_reasons") or "[]")
    reasons_html="".join(f"<li>{html.escape(r)}</li>" for r in reasons)
    companies_html=", ".join(html.escape(c) for c in evidence["companies_strengthened"][:15]) or "none yet"
    jobs_html=" ".join(f"<a href='/job/{jid}'>job</a>" for jid in evidence["matching_job_ids"][:15]) or "none yet"
    evidence_html=(f"<p><b>Matching jobs in current database:</b> {evidence['matching_job_count']}</p>"
        f"<p><b>Role families strengthened:</b> {html.escape(', '.join(evidence['role_families_strengthened']) or 'none')}</p>"
        f"<p><b>Companies where this strengthens fit:</b> {companies_html}</p>"
        f"<p><b>Example matching jobs:</b> {jobs_html}</p>"
        f"<p><b>Skill-gap terms matched:</b> {html.escape(', '.join(f'{k} ({v})' for k,v in evidence['skill_hit_counts'].items()) or 'none')}</p>")
    repo_link=f"<a href='{html.escape(p['repo_url'])}'>{html.escape(p['repo_url'])}</a>" if p.get("repo_url") else "not yet published"
    github_html=(f"<p><b>Repository:</b> {repo_link}</p>"
        f"<p><b>Deployment:</b> {html.escape(p.get('deployment_url') or 'not yet deployed')}</p>"
        f"<p><b>Tech stack:</b> {html.escape(p.get('tech_stack') or p.get('required_skills') or '')}</p>"
        f"<table>{status_html}</table>"
        f"<p><small>No stars/users/performance numbers are shown here unless they actually exist — this section only reports real, verified status.</small></p>")
    body=(f"<h1>{html.escape(p['name'])}</h1><p>Lifecycle: {lifecycle_html}</p>"
        f"<p>Priority score: <b>{p.get('priority_score',0):.1f}</b></p><ul>{reasons_html}</ul>"
        f"<p>Target family: {html.escape(p.get('target_job_family') or '')}</p>"
        f"<h2>GitHub evidence</h2>{github_html}"
        f"<h2>Job-market evidence</h2>{evidence_html}"
        f"<h2>Base repository research</h2><p><b>GitHub base:</b> {html.escape(p.get('github_base_url') or 'none — fresh build')}<br><b>License:</b> {html.escape(p.get('github_base_license') or '')}<br><b>Notes:</b> {html.escape(p.get('github_base_notes') or '')}</p>"
        f"<h2>Specification</h2><pre style='white-space:pre-wrap'>{html.escape(p.get('spec_markdown') or '')}</pre>")
    return page(p["name"],body)

@app.get("/profile",response_class=HTMLResponse)
def profile_evidence():
    profile=load_profile(); cand=profile["candidate"]
    exp=profile.get("experience",[]); projs=profile.get("projects",[]); skills=profile.get("skills",{})
    def _bullets(items,key1,key2):
        return "".join(f"<li><b>{html.escape(x.get(key1,''))}</b> — {html.escape(x.get(key2,''))}<ul>{''.join(f'<li>{html.escape(b)}</li>' for b in x.get('bullets',[]))}</ul></li>" for x in items)
    # Best-effort keyword heuristic for categorizing experience entries by title -- generalized
    # rather than matching one specific person's literal job titles, which would never match
    # anyone else's profile.
    _LEADERSHIP_HINTS=["management head","head of","president","chapter lead","club lead","coordinator","director of operations"]
    def _is_leadership_title(title): t=(title or "").lower(); return any(h in t for h in _LEADERSHIP_HINTS)
    def _is_ambassador_title(title): return "ambassador" in (title or "").lower()
    technical=_bullets([e for e in exp if not _is_leadership_title(e.get("title")) and not _is_ambassador_title(e.get("title"))],"title","company")
    technical+="".join(f"<li><b>{html.escape(p['name'])}</b> — {html.escape(', '.join(p.get('stack',[])))}<ul>{''.join(f'<li>{html.escape(b)}</li>' for b in p.get('bullets',[]))}</ul></li>" for p in projs)
    product_business=_bullets([e for e in exp if _is_leadership_title(e.get("title"))],"title","company")
    communication=_bullets([e for e in exp if _is_ambassador_title(e.get("title"))],"title","company")
    literary_portfolio=cand.get("literary_portfolio")
    humanities_html=(f"<p>{html.escape(literary_portfolio)}</p>" if literary_portfolio else
        "<p><small>No literary/writing portfolio currently on file. This track is exploratory — add a real one (e.g. a link to published writing) to <code>config/profile.json</code> under <code>candidate.literary_portfolio</code> and it will show here and feed into humanities-role eligibility. Nothing is assumed or invented.</small></p>")
    skills_html="".join(f"<p><b>{html.escape(k)}:</b> {html.escape(', '.join(v))}</p>" for k,v in skills.items())
    body=(f"<h1>Career Profile Evidence</h1><p>Organized view of real, already-on-file evidence — nothing here is inferred beyond what's in <code>config/profile.json</code>.</p>"
        f"<h2>Technical</h2><ul>{technical}</ul>{skills_html}"
        f"<h2>Product / Business</h2><ul>{product_business or '<li>No dedicated product/business role on file in config/profile.json.</li>'}</ul>"
        f"<h2>Communication</h2><ul>{communication or '<li>No dedicated communication role on file.</li>'}</ul>"
        f"<h2>Humanities / Literature (exploratory track)</h2>{humanities_html}"
        f"<p><a href='/portfolio'>See portfolio projects building further evidence →</a></p>")
    return page("Career Profile",body)

_ta_counter=[0]
def _ta(label,value):
    _ta_counter[0]+=1; tid=f"paste_field_{_ta_counter[0]}"
    v=html.escape(value or "")
    return (f"<div style='margin:4px 0 14px'><label><b>{html.escape(label)}</b></label> "
        f"<button type='button' onclick=\"navigator.clipboard.writeText(document.getElementById('{tid}').value).then(()=>{{this.textContent='Copied ✓';setTimeout(()=>this.textContent='Copy',1500)}})\">Copy</button>"
        f"<textarea id='{tid}' readonly onclick='this.select()' style='width:100%;min-height:70px;margin-top:4px'>{v}</textarea></div>")

@app.get("/job/{job_id}",response_class=HTMLResponse)
def job_page(job_id):
    j=get_job(job_id)
    if not j:return page("Not found","<h2>Job not found</h2>")
    aid=f"app_{job_id}"; a=get_application(aid) or {}
    resume=(ROOT/"data/applications"/aid/"resume"); resume_versions=sorted([p.name for p in resume.glob("v*")]) if resume.exists() else []
    letters=(ROOT/"data/applications"/aid/"letters"); letter_versions=sorted([p.name for p in letters.glob("v*")]) if letters.exists() else []
    docs=""
    if resume_versions: v=resume_versions[-1]; docs+=f"<p>Tailored résumé ({html.escape(v)}): <a href='/artifact/{aid}/resume/{v}/tailored_resume.pdf'>PDF</a> · <a href='/artifact/{aid}/resume/{v}/tailored_resume.docx'>DOCX</a></p>"
    if letter_versions: v=letter_versions[-1]; docs+=f"<p>Motivation letter ({html.escape(v)}): <a href='/artifact/{aid}/letters/{v}/motivation_letter.pdf'>PDF</a> · <a href='/artifact/{aid}/letters/{v}/motivation_letter.docx'>DOCX</a></p>"
    ps=load_saved_paste_sheet(aid)
    cand=load_profile()["candidate"]
    if ps:
        mode_note="AI-written" if ps.get("generation_mode")=="llm" else "deterministic template (AI unavailable)"
        paste_html=(f"<div class='paste-sheet'><p><small>Generated via {html.escape(mode_note)}. Read it before pasting — it is a draft, not a submit button. Click <b>Copy</b> on any field, then paste into the form.</small></p>"
            +_ta("Full name",cand.get("name",""))
            +_ta("Email",cand.get("email",""))
            +_ta("Phone",cand.get("phone",""))
            +_ta("City",cand.get("city",""))
            +_ta("LinkedIn",cand.get("linkedin",""))
            +_ta("Cover note (paste into the cover letter / message box)",ps.get("cover_note",""))
            +_ta("Why this role",ps.get("why_this_role",""))
            +_ta("Greatest strength",ps.get("greatest_strength",""))
            +_ta("Work authorization",ps.get("work_authorization_answer",""))
            +_ta("Notice period",ps.get("notice_period_answer",""))
            +_ta("Salary expectation",ps.get("salary_expectation_answer",""))
            +f"<form method='post' action='/job/{job_id}/paste-sheet'><button>Regenerate paste sheet</button></form></div>")
    else:
        paste_html=f"<form method='post' action='/job/{job_id}/paste-sheet'><button>Generate paste sheet</button></form><p><small>Contact info, a cover note, and answers to the questions almost every form asks — written to paste straight in. Generate the résumé and letter first so this can link to them.</small></p>"
    applied_html=""
    if a.get("status") in {"SUBMITTED_MANUAL","SUBMITTED_CONFIRMED"}:
        applied_html=f"<p class='ok'><b>Marked applied</b> ({html.escape(a.get('application_method',''))}) on {html.escape(a.get('submitted_at') or '')}</p>"
    else:
        channel_opts="".join(f"<option value='{c}'>{c.replace('_',' ').title()}</option>" for c in SOURCE_CHANNELS)
        applied_html=(f"<form method='post' action='/job/{job_id}/mark-applied'>"
            f"<input name='notes' placeholder='Optional note (e.g. which form fields, referral, etc.)' style='width:50%'> "
            f"<select name='source_channel'><option value=''>Channel (optional)</option>{channel_opts}</select> "
            f"<button>I applied — mark it (official link)</button></form>")
    tier_badge={"QUALIFIED":"🟢 Qualified","TRANSFERABLE":"🔵 Transferable","STRETCH":"🟡 Stretch","MISMATCH":"⚪ Mismatch","EXCLUDED":"⛔ Excluded"}
    tier=j.get("fit_tier") or "MISMATCH"
    elig=None
    try: elig=json.loads(j.get("eligibility_detail") or "null")
    except Exception: elig=None
    if elig:
        rows="".join(f"<tr><td>{html.escape(k.replace('_',' ').title())}</td><td><b>{html.escape(str(v))}</b></td></tr>" for k,v in elig.items() if k not in {"reasons","work_auth_signal"})
        reasons_html="".join(f"<li>{html.escape(r)}</li>" for r in elig.get("reasons",[]))
        elig_html=f"<table>{rows}</table><p><b>Why:</b></p><ul>{reasons_html}</ul>"
    else:
        elig_html="<p><small>Eligibility detail not yet computed for this job — run discovery/score again to populate it.</small></p>"
    strategy_html=""
    if tier in {"QUALIFIED","TRANSFERABLE","STRETCH"}:
        try:
            from .services.application_strategy import build_application_strategy
            st=build_application_strategy(job_id)
            proj=st.get("suggested_portfolio_project")
            proj_html=f"<a href='/portfolio/{proj['id']}'>{html.escape(proj['name'])}</a> ({html.escape(proj['status'])}) — {html.escape(proj['reason'])}" if proj else "No portfolio project matches this role closely enough yet — see <a href='/skill-gaps'>Skill Gaps</a>."
            strategy_html=(f"<p><b>Strongest matching experience:</b> {html.escape(', '.join(st['strongest_experience']) or 'none')}</p>"
                f"<p><b>Strongest matching projects:</b> {html.escape(', '.join(st['strongest_projects']) or 'none')}</p>"
                f"<p><b>Missing requirements (from JD, not in profile):</b> {html.escape(', '.join(st['missing_requirements'][:10]) or 'none flagged')}</p>"
                f"<p><b>Company talking points:</b></p><ul>{''.join(f'<li>{html.escape(t)}</li>' for t in st['company_talking_points'])}</ul>"
                f"<p><b>Suggested portfolio project to showcase:</b> {proj_html}</p>"
                f"<p><b>Interview prep topics:</b></p><ul>{''.join(f'<li>{html.escape(t)}</li>' for t in st['interview_prep_topics'])}</ul>"
                f"<p><b>Networking targets:</b> {html.escape(st['networking_targets'])}</p>")
        except Exception as e:
            strategy_html=f"<p><small>Strategy generation failed: {html.escape(str(e))}</small></p>"
    else:
        strategy_html="<p><small>Strategy is only generated for QUALIFIED/TRANSFERABLE/STRETCH tiers.</small></p>"
    # JD intelligence: hard-constraint preflight, must-have/nice-to-have extraction, evidence
    # gap report and hiring-state wording signals -- all derived from this posting's own text.
    profile=load_profile()
    preflight=hard_constraint_preflight(j, profile)
    constraint_icon={"blocked":"⛔","review":"⚠️","ok":"✓"}
    preflight_html="".join(f"<tr><td>{html.escape(c['constraint'].replace('_',' ').title())}</td><td>{constraint_icon.get(c['status'],'')} {html.escape(c['status'])}</td><td>{html.escape(str({k:v for k,v in c.items() if k not in {'constraint','status'}}))}</td></tr>" for c in preflight["constraints"])
    preflight_html=preflight_html or "<tr><td colspan='3'>No hard-constraint language detected in this posting.</td></tr>"
    state=application_state_signal(j.get("description",""))
    state_html=", ".join(s.replace("_"," ") for s in state["signals"]) or "no evergreen/urgent/rolling language detected"
    gap_rows=requirement_gap_report(j.get("description",""), profile)
    gap_icon={"green":"🟢","amber":"🟡","red":"🔴"}
    gap_html="".join(f"<tr><td>{gap_icon.get(g['status'],'')}</td><td>{html.escape(g['level'].replace('_',' '))}</td><td>{html.escape(g['requirement'][:140])}</td></tr>" for g in gap_rows[:30])
    gap_html=gap_html or "<tr><td colspan='3'>No must-have/nice-to-have phrases detected in this posting's wording.</td></tr>"
    jd_intel_html=(f"<h2>JD intelligence</h2>"
        f"<p><b>Hard-constraint preflight</b> (years, work authorization, language, travel, shift — "
        f"{'⛔ at least one hard block' if preflight['any_blocked'] else 'nothing hard-blocked'}):</p>"
        f"<table><tr><th>Constraint</th><th>Status</th><th>Detail</th></tr>{preflight_html}</table>"
        f"<p><b>Hiring-state wording signal</b> (inference from wording only): {html.escape(state_html)}</p>"
        f"<p><b>Requirement → evidence gap report</b> (🟢 evidence in your profile, 🟡 skill listed but no evidence bullet, 🔴 no match found):</p>"
        f"<table><tr><th></th><th>Level</th><th>Requirement phrase</th></tr>{gap_html}</table>")
    # Priority dimensions (multi-dimensional, never a single opaque score).
    from .services.application_priority import compute_priority_dimensions
    dims=compute_priority_dimensions(j, load_profile())
    dims_html="".join(f"<tr><td>{html.escape(k.replace('_',' ').title())}</td><td>{html.escape(str(v))}</td></tr>" for k,v in dims.items() if not k.endswith('_reason'))
    reasons_html="".join(f"<li>{html.escape(k.replace('_reason','').replace('_',' ').title())}: {html.escape(str(v))}</li>" for k,v in dims.items() if k.endswith('_reason'))
    priority_html=f"<table>{dims_html}</table><p><b>Reasons:</b></p><ul>{reasons_html}</ul>"
    # Ask-a-question (evidence-cited answer engine).
    qa=None
    try:
        qa_path=ROOT/"data/applications"/aid/"qa_answers.json"
        if qa_path.exists(): qa=json.loads(qa_path.read_text(encoding="utf-8"))
    except Exception: qa=None
    qa_html=""
    if qa:
        cited="".join(f"<li>{html.escape(c['claim'])} → {html.escape(', '.join(c['sources']))}</li>" for c in qa.get("cited_claims",[]))
        warn="".join(f"<li>{html.escape(w)}</li>" for w in qa.get("unresolved_warnings",[]))
        qa_html=(f"<p><b>Q:</b> {html.escape(qa['question'])}</p><p><b>A:</b> {html.escape(qa['answer'])}</p>"
            f"<p>Evidence status: <b>{html.escape(qa['evidence_status'])}</b> ({html.escape(qa['generation_mode'])})</p>"
            f"<p><b>Cited claims:</b></p><ul>{cited or '<li>none</li>'}</ul>"
            + (f"<p><b>Review before sending:</b></p><ul>{warn}</ul>" if warn else ""))
    ask_html=(f"<form method='post' action='/job/{job_id}/answer-question'>"
        f"<textarea name='question' placeholder='Paste the exact application question here' style='width:100%;min-height:50px'></textarea>"
        f"<button>Generate evidence-cited answer</button></form>{qa_html}")
    # Outcome tracking.
    outcome_options=["RECRUITER_RESPONSE","ASSESSMENT","INTERVIEW","FINAL","OFFER","REJECTED","WITHDRAWN"]
    outcome_opts_html="".join(f"<option value='{o}'>{o.replace('_',' ').title()}</option>" for o in outcome_options)
    current_outcome=a.get("status") if a.get("status") in outcome_options else None
    reason_opts_html="".join(f"<option value='{r}'{' selected' if a.get('rejection_reason')==r else ''}>{r.replace('_',' ').title()}</option>" for r in REJECTION_REASONS)
    outcome_html=(f"<p>Current: <b>{html.escape(current_outcome or 'no outcome recorded yet')}</b>"
        f"{' (updated '+html.escape(a.get('outcome_updated_at') or '')+')' if a.get('outcome_updated_at') else ''}"
        f"{' · rejection reason: <b>'+html.escape(a.get('rejection_reason'))+'</b>' if a.get('rejection_reason') else ''}</p>"
        f"<form method='post' action='/job/{job_id}/outcome'><select name='outcome'>{outcome_opts_html}</select> "
        f"<select name='rejection_reason'><option value=''>Rejection reason (if applicable)</option>{reason_opts_html}</select> "
        f"<button>Record outcome</button></form>"
        f"<p><small>Never inferred automatically — no email/ATS integration exists. Only recorded when you tell it what actually happened.</small></p>")
    # Cold outreach: contact info only ever pulled from text this project already scraped, never
    # from LinkedIn or a third-party contact database.
    from .services.contact_extraction import contacts_for_job, generate_cold_email_draft
    contacts=contacts_for_job(j)
    if contacts["emails"] or contacts["phones"]:
        emails_html="".join(f"<li>{html.escape(e)}</li>" for e in contacts["emails"])
        phones_html="".join(f"<li>{html.escape(p)}</li>" for p in contacts["phones"])
        cold_html=(f"<p>Found in this posting's own text — not looked up elsewhere:</p>"
            f"<p><b>Emails:</b></p><ul>{emails_html or '<li>none</li>'}</ul>"
            f"<p><b>Phones:</b></p><ul>{phones_html or '<li>none</li>'}</ul>"
            f"<form method='post' action='/job/{job_id}/cold-email'><button>Draft a cold email</button></form>")
        ce_path=ROOT/"data/applications"/aid/"cold_email.json"
        if ce_path.exists():
            try:
                ce=json.loads(ce_path.read_text(encoding="utf-8"))
                cold_html+=(f"<div class='paste-sheet'>{_ta('Subject',ce.get('subject',''))}{_ta('Body',ce.get('body',''))}</div>")
            except Exception: pass
    else:
        cold_html="<p><small>No email or phone number found in this posting's own text. This project does not search LinkedIn or third-party contact databases, so if the posting itself doesn't mention a contact, none is shown.</small></p>"
    body=f"<h1>{html.escape(j['title'])}</h1><p><b>{html.escape(j['company'])}</b> · {html.escape(j['location'])} · {html.escape(j['source'])}</p><p>Fit <b>{j.get('fit_score',0):.0f}</b> · Tier <b>{tier_badge.get(tier,tier)}</b> · Family <b>{html.escape(j.get('role_family',''))}</b> · Friction <b>{html.escape(j.get('application_friction',''))}</b> · Posted <b>{html.escape(j.get('posted_at') or 'unknown')}</b></p><p><a href='{html.escape(j['apply_url'])}' target='_blank'><b>Official application URL →</b></a></p><h2>Priority (multi-dimensional, not a hire-probability)</h2>{priority_html}<h2>Eligibility</h2>{elig_html}{jd_intel_html}<h2>Application strategy</h2>{strategy_html}<h2>Ask a question (evidence-cited)</h2>{ask_html}<h2>Cold outreach</h2>{cold_html}<h2>Job description</h2><pre>{html.escape(j['description'][:15000])}</pre><div class='actions'><form method='post' action='/job/{job_id}/tailor'><button>Tailor CV</button></form><form method='post' action='/job/{job_id}/letter'><button>Generate letter</button></form><form method='post' action='/job/{job_id}/dry-run'><button>Run DRY RUN (automation preview)</button></form></div>{docs}<h2>Paste sheet</h2>{paste_html}<h2>Applied?</h2>{applied_html}<h2>Outcome tracking</h2>{outcome_html}<p class='warning'>Legal/work-authorization, CAPTCHA, MFA and ambiguous screening questions require human review.</p>"; return page(j["title"],body)
@app.post("/job/{job_id}/tailor")
def tailor_route(job_id): tailor(job_id); return RedirectResponse(f"/job/{job_id}",303)
@app.post("/job/{job_id}/letter")
def letter_route(job_id): generate_letter(job_id); return RedirectResponse(f"/job/{job_id}",303)
@app.post("/job/{job_id}/paste-sheet")
def paste_sheet_route(job_id): build_and_save_paste_sheet(job_id); return RedirectResponse(f"/job/{job_id}",303)
@app.post("/job/{job_id}/cold-email")
def cold_email_route(job_id):
    from .services.contact_extraction import generate_cold_email_draft
    j=get_job(job_id)
    ce=generate_cold_email_draft(load_profile(), j)
    aid=f"app_{job_id}"; out=ROOT/"data/applications"/aid; out.mkdir(parents=True,exist_ok=True)
    (out/"cold_email.json").write_text(json.dumps(ce,ensure_ascii=False),encoding="utf-8")
    return RedirectResponse(f"/job/{job_id}",303)
@app.post("/job/{job_id}/mark-applied")
def mark_applied_route(job_id, notes: str = Form(""), source_channel: str = Form("")): mark_applied_manual(job_id, notes, source_channel); return RedirectResponse(f"/job/{job_id}",303)
@app.post("/job/{job_id}/answer-question")
def answer_question_route(job_id, question: str = Form(...)):
    from .services.question_engine import answer_question
    j=get_job(job_id); result=answer_question(question, j, load_profile())
    aid=f"app_{job_id}"; out=ROOT/"data/applications"/aid; out.mkdir(parents=True,exist_ok=True)
    (out/"qa_answers.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return RedirectResponse(f"/job/{job_id}",303)
@app.post("/job/{job_id}/outcome")
def record_outcome_route(job_id, outcome: str = Form(...), rejection_reason: str = Form("")):
    from .services.application_state import transition
    aid=create_application(job_id)
    try:
        transition(aid, outcome, "human-recorded outcome")
    except ValueError as e:
        # Never silently drop this: recording an outcome for a job that was never actually
        # submitted is a real error, not a no-op — the person needs to see it, not a false-positive redirect.
        return page("Could not record outcome", f"<h2>Could not record outcome</h2><p>{html.escape(str(e))}</p><p>An outcome can only be recorded once the application has actually reached a submitted state (SUBMITTED_CONFIRMED, SUBMITTED_MANUAL, or an existing outcome state).</p><p><a href='/job/{job_id}'>← Back to job</a></p>")
    from datetime import datetime, timezone
    fields={"outcome_updated_at":datetime.now(timezone.utc).isoformat()}
    if outcome=="REJECTED" and rejection_reason: fields["rejection_reason"]=rejection_reason
    update_application(aid, **fields)
    return RedirectResponse(f"/job/{job_id}",303)
@app.post("/job/{job_id}/dry-run")
def dry_run(job_id):
    from .services.apply import apply_job; apply_job(job_id,False); return RedirectResponse(f"/job/{job_id}",303)
@app.get('/artifact/{aid}/{kind}/{version}/{filename}')
def artifact(aid,kind,version,filename):
    base=(ROOT/'data/applications').resolve()
    if any('..' in x for x in (aid,kind,version,filename)) or any('/' in x or '\\' in x for x in (aid,kind,version,filename)):
        return HTMLResponse('invalid',400)
    p=(base/aid/kind/version/filename).resolve()
    if base not in p.parents or not p.is_file(): return HTMLResponse('not found',404)
    return FileResponse(p)

@app.get('/qna',response_class=HTMLResponse)
def qna_page():
    rows=qnas(); body="<h1>Reusable Application Q&A</h1><p>Approved factual answers are reused when the same screening question appears. Work authorization, visa, salary and demographic questions remain human-gated.</p><table><tr><th>Category</th><th>Question</th><th>Saved answer</th><th>Approved</th></tr>"+"".join(f"<tr><td>{html.escape(r['category'])}</td><td>{html.escape(r['question'])}</td><td>{html.escape(r['answer'])}</td><td>{'✓' if r['approved'] else '—'}</td></tr>" for r in rows)+"</table><h2>Add / revise answer</h2><form method='post' action='/qna'><input name='question' placeholder='Exact or common question' required style='width:100%'><br><textarea name='answer' placeholder='Factual answer' required style='width:100%;min-height:90px'></textarea><br><input name='category' value='CUSTOM'><button>Save approved answer</button></form>"; return page('Application Q&A',body)

@app.post('/qna')
def qna_save(question:str=Form(...),answer:str=Form(...),category:str=Form('CUSTOM')):
    save_qna(question,answer,1,category); return RedirectResponse('/qna',303)

@app.get("/applications",response_class=HTMLResponse)
def tracker():
    rows=applications(); method_label={"MANUAL_OFFICIAL_LINK":"Manual (official link)","AUTOMATED":"Automated","AUTOMATED_ASSISTED":"Automated + manual submit",'':'—'}
    body="<h1>Application Tracker</h1><p><a href='/export'>Export XLSX + CSV</a></p><table><tr><th>Company</th><th>Role</th><th>Fit</th><th>Status</th><th>Method</th><th>CV</th><th>Letter</th><th>Submitted CV</th><th>Updated</th></tr>"+"".join(f"<tr><td>{html.escape(r['company'])}</td><td>{html.escape(r['title'])}</td><td>{r.get('fit_score',0):.0f}</td><td>{html.escape(r['status'])}</td><td>{html.escape(method_label.get(r.get('application_method') or '',r.get('application_method') or '—'))}</td><td>{html.escape(r.get('resume_version') or '')}<br><a href='/artifact/{r['id']}/resume/{r.get('resume_version') or 'v1'}/tailored_resume.pdf'>PDF</a></td><td>{html.escape(r.get('letter_version') or '')}<br><a href='/artifact/{r['id']}/letters/{r.get('letter_version') or 'v1'}/motivation_letter.pdf'>PDF</a></td><td>{html.escape(r.get('submitted_resume_version') or '')}</td><td>{html.escape(r.get('updated_at',''))}</td></tr>" for r in rows)+"</table>"; return page("Tracker",body)
@app.get("/export")
def export(): x,c=export_tracker(); return FileResponse(x,filename="applications.xlsx")

@app.get("/daily",response_class=HTMLResponse)
def daily_control_center():
    from .db import get_daily_log, daily_log_history, set_daily_target
    profile=load_profile()
    today=get_daily_log()
    apps=applications(2000)
    day_str=today["day"]
    applied_today=[a for a in apps if (a.get("submitted_at") or "").startswith(day_str) or (a.get("updated_at") or "").startswith(day_str) and a.get("status") in {"SUBMITTED_CONFIRMED","SUBMITTED_MANUAL"}]
    automated=sum(1 for a in applied_today if a.get("application_method") in {"AUTOMATED","AUTOMATED_ASSISTED"})
    manual=sum(1 for a in applied_today if a.get("application_method")=="MANUAL_OFFICIAL_LINK")
    blocked=sum(1 for a in apps if a.get("status")=="REQUIRES_HUMAN" and (a.get("updated_at") or "").startswith(day_str))
    qualified=sum(1 for a in applied_today if a.get("fit_tier")=="QUALIFIED")
    transferable=sum(1 for a in applied_today if a.get("fit_tier")=="TRANSFERABLE")
    target=today.get("target") or profile.get("preferences",{}).get("daily_application_target",30)
    metrics=[
        ("Target", target), ("Discovered today", today.get("discovered",0)), ("Eligible today", today.get("eligible",0)),
        ("Applied today", len(applied_today)), ("Automated", automated), ("Human-assisted/manual", manual),
        ("Blocked (human required)", blocked), ("Qualified-tier applications", qualified), ("Transferable-tier applications", transferable),
    ]
    metrics_html="".join(f"<tr><td>{html.escape(k)}</td><td><b>{v}</b></td></tr>" for k,v in metrics)
    history=daily_log_history(30)
    hist_rows=""
    for h in history:
        day_apps=[a for a in apps if (a.get("submitted_at") or "").startswith(h["day"])]
        hist_rows+=f"<tr><td>{html.escape(h['day'])}</td><td>{h.get('target',0)}</td><td>{len(day_apps)}</td><td>{h.get('discovered',0)}</td><td>{h.get('eligible',0)}</td></tr>"
    from .services.track_analytics import track_performance_summary, track_performance_by_channel, rejection_reasons_breakdown
    perf=track_performance_summary()
    channel_perf=track_performance_by_channel()
    rejection_breakdown=rejection_reasons_breakdown()
    def _track_rows(buckets):
        rows=""
        for b in buckets:
            resp=f"{b['response_rate_pct']}%" if b['response_rate_pct'] is not None else (b['note'] or "n/a")
            interview=f"{b['interview_rate_pct']}%" if b['interview_rate_pct'] is not None else "n/a"
            rows+=(f"<tr><td>{html.escape(b['track'])}</td><td>{b['applications']}</td><td>{b['submitted']}</td>"
                   f"<td>{b['responded']}</td><td>{b['interviewed']}</td><td>{b['offered']}</td><td>{b['rejected']}</td>"
                   f"<td>{html.escape(resp)}</td><td>{html.escape(interview)}</td></tr>")
        return rows or "<tr><td colspan='9'>No applications tracked yet.</td></tr>"
    track_header="<tr><th>Track</th><th>Applications</th><th>Submitted</th><th>Responded</th><th>Interviewed</th><th>Offered</th><th>Rejected</th><th>Response rate</th><th>Interview rate</th></tr>"
    conclusions_note=("Enough submitted applications exist to start comparing tracks." if perf["enough_data_for_conclusions"]
        else f"Only {perf['total_submitted']} submitted applications tracked so far — too few to draw conclusions about which track performs best. Keep applying across tracks; this table fills in as real outcomes come back.")
    from .services.auto_apply import eligible_jobs
    automatable_pool=len(eligible_jobs(limit=500))
    automate_bar=(f"<div class='automate-bar'>"
        f"<b>Automate Apply</b> — {automatable_pool} jobs currently eligible (QUALIFIED/TRANSFERABLE, "
        f"on a non-CAPTCHA-proven ATS, not yet applied to). Dry run fills and screenshots forms "
        f"without submitting anything. Real submission still respects the {daily_cap() or 'unlimited'}/day cap "
        f"and stops short (REQUIRES_HUMAN) on any job where a CAPTCHA is detected.<br>"
        f"<form method='post' action='/daily/automate-apply' style='margin-top:6px'>"
        f"Count: <input type='number' name='count' value='10' min='1' max='{max(automatable_pool,1)}' style='width:70px'> "
        f"<label><input type='radio' name='mode' value='dry_run' checked> Dry run (recommended first)</label> "
        f"<label><input type='radio' name='mode' value='real'> Real submission</label> "
        f"<button>Run</button></form></div>")
    body=(f"<h1>Daily Control Center</h1><p>Immediately answers: did I actually apply today, and to what quality of job — never inferred, never a manufactured quota.</p>"
        f"<form method='post' action='/daily/set-target'>Daily target: <input type='number' name='target' value='{target}' style='width:80px'> <button>Update</button></form>"
        f"{automate_bar}"
        f"<h2>Today ({html.escape(day_str)})</h2><table>{metrics_html}</table>"
        f"<h2>History</h2><table><tr><th>Date</th><th>Target</th><th>Applied</th><th>Discovered</th><th>Eligible</th></tr>{hist_rows}</table>"
        f"<h2>Track Performance</h2><p><small>{html.escape(conclusions_note)} Rates only shown once a track has at least 5 submitted applications — below that, a percentage would be noise, not signal.</small></p>"
        f"<h3>By role family / track</h3><table>{track_header}{_track_rows(perf['by_role_family'])}</table>"
        f"<h3>By country</h3><table>{track_header}{_track_rows(perf['by_country'])}</table>"
        f"<h3>By source channel (FP06)</h3><table>{track_header}{_track_rows(channel_perf)}</table>"
        f"<p><small>\"Applied\" only ever counts an application whose status is SUBMITTED_CONFIRMED or SUBMITTED_MANUAL — never a discovered, prepared or failed one. Channel is only recorded when set on the \"I applied\" form.</small></p>"
        f"<h2>Rejection reasons (FP13)</h2>"
        + ("<table><tr><th>Reason</th><th>Count</th></tr>"+"".join(f"<tr><td>{html.escape(r['reason'].replace('_',' ').title())}</td><td>{r['count']}</td></tr>" for r in rejection_breakdown)+"</table>" if rejection_breakdown else "<p><small>No rejections recorded yet.</small></p>")
        + "<p><small>Patterns across many rejections are informative; a single rejection is not. Recorded only when a human sets the outcome.</small></p>")
    return page("Daily Control Center", body)

@app.post("/daily/automate-apply",response_class=HTMLResponse)
def automate_apply_route(count: int = Form(...), mode: str = Form(...)):
    from .services.auto_apply import run_batch
    real=(mode=="real")
    r=run_batch(count,real_apply=real)
    def _row(d):
        return f"<tr><td>{html.escape(d['status'])}</td><td>{html.escape(d.get('company') or '?')}</td><td>{html.escape(d.get('title') or '?')}</td><td><a href='/job/{html.escape(d['job_id'])}'>view</a></td>{('<td>'+html.escape(d['error'])+'</td>') if d.get('error') else '<td></td>'}</tr>"
    rows="".join(_row(d) for d in r["details"]) or "<tr><td colspan='5'>No eligible jobs were found to attempt.</td></tr>"
    headline=f"Submitted: {r['submitted']} &nbsp; Dry-run filled: {r['dry_run']} &nbsp; Needs human (CAPTCHA/review): {r['requires_human']} &nbsp; Failed: {r['failed']}"
    cap_note="<p><b>Daily submission cap reached — stopped early.</b></p>" if r["cap_reached"] else ""
    body=(f"<h1>Automate Apply — results</h1>"
        f"<p>Mode: {'<b>REAL SUBMISSION</b>' if real else 'Dry run (nothing submitted)'}. Requested {r['requested']}, checked {r['eligible_pool_checked']} eligible jobs.</p>"
        f"<p>{headline}</p>{cap_note}"
        f"<table><tr><th>Status</th><th>Company</th><th>Title</th><th></th><th>Error</th></tr>{rows}</table>"
        f"<p><a href='/daily'>Back to Daily Control Center</a></p>")
    return page("Automate Apply — results", body)

@app.post("/daily/set-target")
def set_daily_target_route(target: int = Form(...)):
    from .db import set_daily_target
    set_daily_target(target); return RedirectResponse("/daily",303)

@app.get("/resume",response_class=HTMLResponse)
def resume_page():
    master=ROOT/"data/master"; files=[p.name for p in master.iterdir() if p.is_file()]
    links="".join(f"<li>{html.escape(x)}" + (f" — <a href='/resume/forensics/{x}'>Run forensics</a>" if Path(x).suffix.lower() in {'.pdf','.docx','.txt','.md'} else "") + "</li>" for x in files)
    body="<h1>Resume</h1><p>Upload PDF/DOCX/TXT/MD to inspect it locally. Upload does not overwrite config/profile.json.</p><form method='post' action='/resume' enctype='multipart/form-data'><input type='file' name='resume' accept='.pdf,.docx,.txt,.md' required><button>Import / inspect</button></form><h2>Master files</h2><ul>"+links+"</ul>"; return page("Resume",body)

def _forensics_html(result):
    pt=result["plain_text"]; warn="".join(f"<li>{html.escape(w)}</li>" for w in pt["warnings"]) or "<li>none</li>"
    glyphs=result["glyphs"]
    glyph_html="".join(f"<tr><td><code>{html.escape(g['codepoint'])}</code></td><td>{g['count']}</td><td><code>{html.escape(g['context'])}</code></td></tr>" for g in glyphs[:25]) or "<tr><td colspan='3'>None found — text extracted cleanly.</td></tr>"
    fn=result["filename"]; fn_issues="".join(f"<li>{html.escape(i)}</li>" for i in fn["issues"]) or "<li>none — filename looks clean</li>"
    m=result["ats_mirror"]
    mirror_html=(f"<p><b>Name guess (first line):</b> {html.escape(m['name_guess'] or '—')}</p>"
        f"<p><b>Emails found:</b> {html.escape(', '.join(m['emails']) or 'none')}</p>"
        f"<p><b>Phones found:</b> {html.escape(', '.join(m['phones']) or 'none')}</p>"
        f"<p><b>Links found:</b> {html.escape(', '.join(m['links']) or 'none')}</p>"
        f"<p><b>Section headers detected:</b> {html.escape(', '.join(m['section_headers_detected']) or 'none'  )}</p>"
        f"<p><b>Missing core sections:</b> {html.escape(', '.join(m['missing_core_sections']) or 'none')}</p>")
    cons=result["consistency"]
    cons_html="".join(f"<tr><td>{html.escape(c['section'])}</td><td>{html.escape(c['entity'])}</td><td>{html.escape(c['title'])}</td><td>{'✓' if c['entity_found_in_resume'] else '⚠️'}</td><td>{html.escape(c['flag'] or 'consistent')}</td></tr>" for c in cons) or "<tr><td colspan='5'>No profile loaded to check against.</td></tr>"
    links_section=""
    if result.get("links") is not None:
        lk=result["links"]
        icon={"ok":"✓","redirect":"↪","login_or_blocked":"🔒","dead":"✗","error":"⚠️","unreachable":"✗"}
        rows="".join(f"<tr><td>{html.escape(l['url'])}</td><td>{icon.get(l['status'],'')} {html.escape(l['status'])}</td><td>{html.escape(l['detail'])}</td></tr>" for l in lk) or "<tr><td colspan='3'>No links found.</td></tr>"
        links_section=f"<h3>Link survivability (RF11)</h3><table><tr><th>URL</th><th>Status</th><th>Detail</th></tr>{rows}</table>"
    else:
        links_section="<h3>Link survivability (RF11)</h3><p><small>Not checked — add ?check_links=1 to the forensics URL to click every link found.</small></p>"
    return (f"<h3>Plain-text reality check (RF01)</h3><p>{pt['char_count']} characters, {pt['non_empty_line_count']} non-empty lines.</p><ul>{warn}</ul>"
        f"<h3>Filename discipline (RF05)</h3><p><code>{html.escape(fn['filename'])}</code></p><ul>{fn_issues}</ul>"
        + (f"<p><small>Suggested: <code>{html.escape(fn['suggested_filename'])}</code></small></p>" if fn.get("suggested_filename") else "")
        + f"<h3>Glyph compatibility scan (RF04)</h3><table><tr><th>Codepoint</th><th>Count</th><th>Context</th></tr>{glyph_html}</table>"
        f"<h3>ATS extraction mirror (RF02)</h3>{mirror_html}"
        f"<h3>Consistency checksum vs profile (RF13)</h3><table><tr><th>Section</th><th>Entity</th><th>Title</th><th>Found</th><th>Flag</th></tr>{cons_html}</table>"
        f"{links_section}"
        f"<details><summary>Plain-text view (what a text-only renderer sees)</summary><pre>{html.escape(pt['text'][:15000])}</pre></details>")

@app.get("/resume/forensics/{filename}",response_class=HTMLResponse)
def resume_forensics_route(filename, check_links: int = 0):
    from .services.resume_forensics import run_all
    p=(ROOT/"data/master"/filename).resolve()
    base=(ROOT/"data/master").resolve()
    if base not in p.parents or not p.is_file(): return HTMLResponse("not found",404)
    profile=load_profile()
    try:
        result=run_all(p, candidate_name=profile.get("candidate",{}).get("name",""), profile=profile, check_links=bool(check_links))
    except Exception as e:
        return page("Resume forensics", f"<h1>Resume forensics</h1><p>Could not analyze this file: {html.escape(str(e))}</p>")
    body=f"<h1>Resume forensics: {html.escape(filename)}</h1><p><a href='/resume'>← back to Resume</a> · <a href='/resume/forensics/{filename}?check_links=1'>Run with link checking</a></p>{_forensics_html(result)}"
    return page("Resume forensics", body)

@app.post("/resume",response_class=HTMLResponse)
async def resume_upload(resume: UploadFile=File(...)):
    suffix=Path(resume.filename or '').suffix.lower()
    if suffix not in {'.pdf','.docx','.txt','.md'}: return page("Resume","<p>Unsupported format.</p>")
    tmp=ROOT/"data/master"/("_upload"+suffix); tmp.write_bytes(await resume.read())
    try:
        dst,txt,n=import_resume(tmp); tmp.unlink(missing_ok=True)
        from .services.resume_forensics import run_all, filename_check
        profile=load_profile()
        # Filename discipline (RF05) is checked against the *original* uploaded filename --
        # import_resume() renames it on disk, so that's the only place it's still available.
        result=run_all(dst, candidate_name=profile.get("candidate",{}).get("name",""), profile=profile, check_links=False)
        result["filename"]=filename_check(resume.filename or "", profile.get("candidate",{}).get("name",""))
        return page("Resume",f"<h1>Imported</h1><p>{html.escape(dst)}</p><p>Extracted {n} characters to <code>{html.escape(txt)}</code>.</p><p>Master profile remains unchanged until you deliberately edit config/profile.json.</p><h2>Forensics (auto-run on upload)</h2>{_forensics_html(result)}")
    except Exception as e:
        tmp.unlink(missing_ok=True); return page("Resume",f"<p>Could not inspect resume: {html.escape(str(e))}</p>")
@app.get("/settings",response_class=HTMLResponse)
def settings(): return page("Safety","<h1>Safety</h1><ul><li>Browser profile: <code>data/browser-profile</code></li><li>Normal Chrome profile is never accepted.</li><li>Default: DRY_RUN.</li><li>No CAPTCHA/MFA bypass.</li><li>REAL_APPLY requires an explicit per-job token.</li><li>Hard daily submission cap: <code>{daily_cap() or 'disabled'}</code>; submitted today: <code>{submitted_today()}</code>.</li><li>Private/loopback application destinations are blocked.</li><li>Submission requires positive confirmation evidence.</li><li>Run <code>python -m app.cli setup</code> for first-run profile setup.</li><li>Run <code>python -m app.cli seed-qna</code> to preload reusable application answers.</li><li>Country targeting covers Denmark, Belgium, Finland, Switzerland, Poland, Sweden, Estonia, Ireland, Singapore and wider Europe/UK.</li></ul>")
