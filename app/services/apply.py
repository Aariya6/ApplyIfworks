import datetime,hashlib,json,re
from pathlib import Path
from ..db import create_application,get_job,get_application,update_application,log_event,add_evidence
from .tailor import ROOT,load_profile
from .screening import analyze_questions, approved_answer
from .application_state import transition
from .security import browser_profile_path,validate_application_url,validate_redirect
from .rate_limit import assert_can_submit
DANGEROUS_MARKERS=["captcha","recaptcha","hcaptcha","verify you are human","cloudflare","multi-factor","two-factor","authentication code","security challenge"]
CONFIRMATION_MARKERS=["thank you","application received","successfully submitted","application submitted","confirmation number","application id"]

def has_submission_confirmation(text):
    """Return True only when the page contains a strong submission marker."""
    body=(text or "").lower()
    return any(x in body for x in CONFIRMATION_MARKERS)

def safe_profile():
    p=browser_profile_path(); p.mkdir(parents=True,exist_ok=True); return p

def browser_launch_kwargs():
    """Return a deterministic, isolated Chromium launch configuration.

    The executable can be supplied explicitly for CI/container environments; the
    browser profile is always confined to data/browser-profile by safe_profile().
    """
    import os, shutil
    executable=os.getenv("RJP_CHROMIUM_EXECUTABLE") or shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    kwargs={"headless":False,"accept_downloads":False,"args":["--no-sandbox"]}
    if executable: kwargs["executable_path"]=executable
    return kwargs

def field_value(profile,kind):
    c=profile["candidate"]; return {"email":c.get("email"),"phone":c.get("phone"),"first":c.get("name","").split()[0],"last":" ".join(c.get("name","").split()[1:]),"linkedin":c.get("linkedin"),"city":c.get("city")}.get(kind)

def detect_fields(page):
    fields=[]; loc=page.locator("input,textarea,select")
    for i in range(min(loc.count(),200)):
        try:
            e=loc.nth(i)
            if not e.is_visible(): continue
            attrs={k:e.get_attribute(k) or "" for k in ["name","id","placeholder","aria-label","type"]}; label=" ".join(attrs.values()).lower(); kind="unknown"
            for k,terms in {"email":["email","e-mail"],"phone":["phone","mobile","telephone"],"first":["first name","firstname","given name"],"last":["last name","lastname","family name","surname"],"linkedin":["linkedin"],"city":["city","location"]}.items():
                if any(t in label for t in terms): kind=k; break
            fields.append({"index":i,"kind":kind,"attrs":attrs})
        except Exception: pass
    return fields

def _dismiss_cookie_consent(page):
    """Confirmed live on a real Workable posting: an undismissed cookie-consent dialog's backdrop
    intercepts every click on the underlying page -- including the landing 'Apply' button -- so
    Playwright's click silently retries against a blocked target until it times out. A real human
    applicant would click through this without a second thought; do the same before attempting any
    other interaction on the page."""
    for t in ["accept all","accept cookies","accept","i agree","allow all","got it","ok"]:
        try:
            b=page.get_by_role("button",name=re.compile(rf"^{re.escape(t)}$",re.I))
            if b.count()==1 and b.first.is_visible():
                b.first.click(timeout=3000); page.wait_for_timeout(300); return True
        except Exception: pass
    return False

def _maybe_click_apply_landing(page):
    """Some ATS platforms (confirmed live: Ashby, Workable) gate the real application form
    behind an initial 'Apply' button on a job-description landing page -- the apply_url itself
    doesn't lead straight to a fillable form. If the first field-detection pass finds nothing,
    look for exactly one visible control whose text is unambiguously an apply action, click it,
    and let the caller re-run field detection on whatever loads next. Same discipline as the
    final submit click: never guess when more than one candidate matches."""
    candidates=[]
    for sel in ["button","a"]:
        loc=page.locator(sel)
        for i in range(min(loc.count(),150)):
            try:
                b=loc.nth(i); t=(b.inner_text() or b.get_attribute("value") or "").strip().lower()
                if re.search(r"^(apply|apply now|apply for this job|apply for this position|apply for this role)$",t) and b.is_visible() and b.is_enabled():
                    candidates.append(b)
            except Exception: pass
    if len(candidates)!=1: return False
    try:
        candidates[0].click(); page.wait_for_timeout(1500)
        try: page.wait_for_load_state("domcontentloaded",timeout=15000)
        except Exception: pass
        return True
    except Exception:
        return False

def _resume_candidates(aid): return sorted((ROOT/"data/applications"/aid/"resume").glob("v*/tailored_resume.pdf"))
def _letter_candidates(aid): return sorted((ROOT/"data/applications"/aid/"letters").glob("v*/motivation_letter.pdf"))

def _manual_submit_handoff(aid, page, evidence, resumes):
    """Human-in-the-loop handoff for CAPTCHA/bot-check pages.

    The form has already been filled (resume, letter, fields, reusable Q&A).
    The visible browser window stays open; the person solves the challenge
    and clicks the real Submit button themselves. We never solve, bypass or
    script around the challenge. Afterward we only *observe* the resulting
    page and log what we can actually verify.
    """
    print("\n" + "="*70)
    print("VERIFICATION REQUIRED (CAPTCHA / bot-check detected).")
    print("The application has been filled with your tailored resume, letter")
    print("and reusable answers where possible. A visible browser window is open.")
    print("  1) Solve the verification challenge yourself in that window.")
    print("  2) Review every field, then click the real Submit button yourself.")
    print("  3) Come back here and press Enter once you have submitted.")
    print("="*70)
    try:
        input("Press Enter after you have submitted (or Ctrl+C to abort without submitting): ")
    except KeyboardInterrupt:
        transition(aid,"REQUIRES_REVIEW","aborted during manual captcha/submit step")
        return {"status":"REQUIRES_REVIEW","reason":"aborted by user before manual submit"}
    transition(aid,"READY_TO_SUBMIT","human verification/submit acknowledged"); transition(aid,"SUBMITTING","manual submit click reported by user")
    page.wait_for_timeout(500)
    page.screenshot(path=str(evidence/"after_manual_submit.png"),full_page=True); add_evidence(aid,"screenshot",str(evidence/"after_manual_submit.png"))
    text=(page.locator("body").inner_text(timeout=10000) or "").lower(); url=page.url
    if has_submission_confirmation(text):
        r=resumes[-1] if resumes else None; rh=hashlib.sha256(r.read_bytes()).hexdigest() if r else None
        transition(aid,"SUBMITTED_CONFIRMED","manual submission with confirmation evidence")
        update_application(aid,submitted_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),evidence_path=str(evidence),submitted_resume_version=r.parent.name if r else None,submitted_resume_hash=rh,submitted_resume_filename=r.name if r else None,application_method="AUTOMATED_ASSISTED")
        add_evidence(aid,"confirmation_url",value=url); return {"status":"SUBMITTED_CONFIRMED","evidence":str(evidence),"url":url}
    transition(aid,"SUBMIT_CLICKED_REVIEW","manual submission without strong confirmation text on the page")
    return {"status":"SUBMIT_CLICKED_REVIEW","evidence":str(evidence),"url":url,"note":"Could not detect a strong confirmation message. Verify manually and update the tracker if it went through."}

def _safe_fill_value(control, answer):
    if answer is None: return False
    try:
        typ=(control.get_attribute("type") or "").lower()
        if typ in {"checkbox","radio","file","hidden"}: return False
        if control.get_attribute("disabled") is not None: return False
        tag=control.evaluate("e=>e.tagName.toLowerCase()")
        if tag=="select":
            opts=control.locator("option"); val=str(answer).strip().lower()
            for i in range(opts.count()):
                o=opts.nth(i); label=(o.inner_text() or "").strip(); oval=(o.get_attribute("value") or "").strip()
                if label.lower()==val or oval.lower()==val or val in label.lower():
                    control.select_option(oval or label); return True
            return False
        control.fill(str(answer))
        return control.input_value()==str(answer)
    except Exception:
        return False

def _fill_reusable_qna(page, questions, profile):
    filled=[]
    for q in questions:
        ans,conf=approved_answer(q,profile)
        if ans is None or conf < 0.95: continue
        try:
            loc=page.get_by_label(q, exact=False)
            if loc.count()==1 and loc.first.is_visible() and _safe_fill_value(loc.first,ans):
                filled.append(q)
                continue
        except Exception: pass
        # Fallback: locate a visible text control whose accessible metadata matches the question.
        controls=page.locator("input,textarea,select")
        for i in range(min(controls.count(),200)):
            try:
                e=controls.nth(i)
                if not e.is_visible(): continue
                attrs={k:(e.get_attribute(k) or "") for k in ["name","id","placeholder","aria-label"]}
                blob=" ".join(attrs.values()).lower()
                ql=q.lower()
                terms=[t for t in re.findall(r"[a-z]{4,}",ql) if t not in {"what","your","which","where","does","have","this","that","with","from"}]
                if terms and sum(t in blob for t in terms)>=max(1,min(2,len(terms))):
                    if _safe_fill_value(e,ans): filled.append(q); break
            except Exception: pass
    return filled

def mark_applied_manual(job_id,notes=""):
    """Record that the person applied themselves through the official link. No automation
    touched the target site for this submission — that honesty is the whole point of the
    distinction from SUBMITTED_CONFIRMED/AUTOMATED."""
    job=get_job(job_id)
    if not job: raise ValueError("Unknown job")
    aid=create_application(job_id)
    existing=get_application(aid)
    if existing and existing.get("status") in {"SUBMITTED_CONFIRMED","SUBMITTED_MANUAL"}:
        return {"status":"ALREADY_SUBMITTED","application_id":aid}
    transition(aid,"SUBMITTED_MANUAL","applied by the candidate via the official link")
    r=_resume_candidates(aid); r=r[-1] if r else None
    rh=hashlib.sha256(r.read_bytes()).hexdigest() if r else None
    update_application(aid,submitted_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        application_method="MANUAL_OFFICIAL_LINK",notes=notes,
        submitted_resume_version=r.parent.name if r else None,submitted_resume_hash=rh,submitted_resume_filename=r.name if r else None)
    log_event(aid,"SUBMITTED_MANUAL",notes or "marked applied via official link")
    return {"status":"SUBMITTED_MANUAL","application_id":aid}

def apply_job(job_id,real_apply=False,confirm_token=None,batch_mode=False):
    job=get_job(job_id)
    if not job: raise ValueError("Unknown job")
    aid=create_application(job_id); safe_profile()
    existing=__import__('app.db',fromlist=['get_application']).get_application(aid)
    if existing and existing.get("status")=="SUBMITTED_CONFIRMED":
        return {"status":"ALREADY_SUBMITTED","application_id":aid,"reason":"Duplicate application prevented"}
    if real_apply and confirm_token!=f"CONFIRM-{job_id}": raise PermissionError("Explicit per-application confirmation token required")
    if not job.get("apply_url"): transition(aid,"REQUIRES_REVIEW","No official application URL"); return {"status":"REQUIRES_REVIEW","reason":"No official application URL"}
    validate_application_url(job["apply_url"])
    from playwright.sync_api import sync_playwright
    evidence=ROOT/"data/evidence"/aid; evidence.mkdir(parents=True,exist_ok=True); profile=load_profile()
    if (getattr(__import__('os'),'environ').get('RJP_REQUIRE_TAILORED_RESUME','1')=='1' and not _resume_candidates(aid)):
        transition(aid,'REQUIRES_REVIEW','Generate a tailored resume before application'); return {'status':'REQUIRES_REVIEW','reason':'No tailored resume'}
    if (getattr(__import__('os'),'environ').get('RJP_REQUIRE_TAILORED_LETTER','0')=='1' and not _letter_candidates(aid)):
        transition(aid,'REQUIRES_REVIEW','Generate a motivation letter before application'); return {'status':'REQUIRES_REVIEW','reason':'No motivation letter'}
    transition(aid,"READY","application prepared")
    with sync_playwright() as p:
        context=p.chromium.launch_persistent_context(str(safe_profile()),**browser_launch_kwargs())
        page=context.pages[0] if context.pages else context.new_page()
        try:
            transition(aid,"BROWSER_OPENED",job["apply_url"]); log_event(aid,"BROWSER_OPENED",job["apply_url"])
            page.goto(job["apply_url"],wait_until="domcontentloaded",timeout=60000)
            validate_redirect(page.url)
            if _dismiss_cookie_consent(page): log_event(aid,"COOKIE_CONSENT_DISMISSED","accepted so it stops blocking clicks on the real page")
            page.screenshot(path=str(evidence/"before_fill.png"),full_page=True); add_evidence(aid,"screenshot",str(evidence/"before_fill.png"))
            body=(page.locator("body").inner_text(timeout=10000) or "").lower()
            captcha_flagged=any(m in body for m in DANGEROUS_MARKERS)
            if captcha_flagged:
                add_evidence(aid,"block_reason",value="captcha_or_mfa_detected"); log_event(aid,"CAPTCHA_DETECTED","continuing to fill the form; manual solve+submit will be required")
            # Confirmed live on real Ashby postings: the application form is a client-rendered SPA
            # that has not hydrated the instant domcontentloaded fires, so detecting fields with no
            # wait at all finds zero even though the form loads correctly moments later. Wait for at
            # least one real field to appear before giving up on this page having any.
            try: page.wait_for_selector("input,textarea,select",timeout=5000)
            except Exception: pass
            fields=detect_fields(page)
            if not fields and _maybe_click_apply_landing(page):
                # Confirmed live on real Workable postings: the apply_url lands on a job-description
                # page with an "Apply for this job" control gating the real form, not the form itself.
                log_event(aid,"APPLY_LANDING_CLICKED","clicked an unambiguous initial Apply control before the real form loaded")
                try: page.wait_for_selector("input,textarea,select",timeout=5000)
                except Exception: pass
                fields=detect_fields(page)
            transition(aid,"FORM_ANALYZED",f"{len(fields)} visible fields")
            filled=[]
            for f in fields:
                value=field_value(profile,f["kind"])
                if not value: continue
                try:
                    e=page.locator("input,textarea,select").nth(f["index"]); typ=(f["attrs"].get("type") or "").lower()
                    if typ not in {"checkbox","radio","file","hidden"} and e.is_enabled():
                        e.fill(value)
                        if hasattr(e,'input_value') and e.input_value()!=value: raise RuntimeError("field verification failed")
                        filled.append(f["kind"])
                except Exception: pass
            resumes=_resume_candidates(aid); letters=_letter_candidates(aid); inputs=page.locator("input[type='file']")
            if resumes and inputs.count(): inputs.first.set_input_files(str(resumes[-1].resolve())); filled.append("resume_upload")
            if letters and inputs.count()>1: inputs.nth(1).set_input_files(str(letters[-1].resolve())); filled.append("letter_upload")
            qs=[]
            for sel in ["label","legend"]:
                ll=page.locator(sel)
                for i in range(min(ll.count(),150)):
                    try:
                        t=(ll.nth(i).inner_text() or "").strip()
                        if "?" in t and 3<len(t)<500: qs.append(t)
                    except Exception: pass
            unique_questions=list(dict.fromkeys(qs))
            qres=analyze_questions(aid,unique_questions,profile) if unique_questions else []
            qna_filled=_fill_reusable_qna(page,unique_questions,profile) if unique_questions else []
            if any(x["status"]=="REQUIRES_HUMAN" for x in qres):
                page.screenshot(path=str(evidence/"requires_human.png"),full_page=True); transition(aid,"REQUIRES_HUMAN","screening question requires user input"); return {"status":"REQUIRES_HUMAN","questions":qres,"evidence":str(evidence)}
            page.screenshot(path=str(evidence/"after_fill.png"),full_page=True); transition(aid,"FORM_FILLED",json.dumps({"fields":filled,"reusable_qna_filled":qna_filled}));
            if not real_apply:
                transition(aid,"DRY_RUN","submit blocked"); return {"status":"DRY_RUN","filled":filled,"evidence":str(evidence),"captcha_detected":captcha_flagged}
            # The explicit token is the final submission approval. It is checked
            # again immediately before any submit control is clicked.
            if confirm_token!=f"CONFIRM-{job_id}":
                transition(aid,"REQUIRES_REVIEW","explicit submission approval missing")
                return {"status":"REQUIRES_REVIEW","reason":"Explicit submission approval required","evidence":str(evidence)}
            assert_can_submit()
            if captcha_flagged:
                if batch_mode:
                    # Unattended batch runs never wait on a human at the terminal -- that's the
                    # whole point of batch_mode. The form stays filled and evidenced; the job is
                    # left for a person to finish (or for a normal, non-batch apply_job call) so
                    # automation only ever auto-completes the genuinely non-CAPTCHA cases.
                    page.screenshot(path=str(evidence/"captcha_requires_human.png"),full_page=True)
                    transition(aid,"REQUIRES_HUMAN","captcha/bot-check detected during batch run; form filled, awaiting manual solve+submit")
                    return {"status":"REQUIRES_HUMAN","reason":"captcha_or_mfa_detected","evidence":str(evidence)}
                return _manual_submit_handoff(aid,page,evidence,resumes)
            buttons=page.locator("button,input[type='submit'],a"); candidates=[]
            for i in range(min(buttons.count(),150)):
                try:
                    b=buttons.nth(i); t=(b.inner_text() or b.get_attribute("value") or "").strip().lower()
                    if re.search(r"^(submit|apply|send application|submit application)$",t) and b.is_visible() and b.is_enabled(): candidates.append(b)
                except Exception: pass
            if len(candidates)!=1:
                # Log what was actually found -- "ambiguous" alone gave no way to tell 0-match from
                # 2+-match, or what text those controls had, when this needed debugging for real.
                found_texts=[]
                for c in candidates[:10]:
                    try: found_texts.append((c.inner_text() or c.get_attribute("value") or "").strip())
                    except Exception: pass
                log_event(aid,"SUBMIT_CONTROL_AMBIGUOUS",f"{len(candidates)} candidates: {found_texts}")
                transition(aid,"REQUIRES_REVIEW","submit control ambiguous"); return {"status":"REQUIRES_REVIEW","candidates_found":len(candidates)}
            transition(aid,"READY_TO_SUBMIT","explicit token accepted"); transition(aid,"SUBMITTING","submit clicked")
            candidates[0].click(); page.wait_for_timeout(1500); validate_redirect(page.url)
            page.screenshot(path=str(evidence/"after_submit.png"),full_page=True); add_evidence(aid,"screenshot",str(evidence/"after_submit.png"))
            text=(page.locator("body").inner_text(timeout=10000) or "").lower(); url=page.url
            confirmed=has_submission_confirmation(text)
            if confirmed:
                r=resumes[-1] if resumes else None; rh=hashlib.sha256(r.read_bytes()).hexdigest() if r else None
                transition(aid,"SUBMITTED_CONFIRMED","strong confirmation evidence")
                update_application(aid,submitted_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),evidence_path=str(evidence),submitted_resume_version=r.parent.name if r else None,submitted_resume_hash=rh,submitted_resume_filename=r.name if r else None,application_method="AUTOMATED")
                add_evidence(aid,"confirmation_url",value=url); return {"status":"SUBMITTED_CONFIRMED","evidence":str(evidence),"url":url}
            transition(aid,"SUBMIT_CLICKED_REVIEW","No strong confirmation evidence"); return {"status":"SUBMIT_CLICKED_REVIEW","evidence":str(evidence),"url":url}
        except Exception as e:
            try: transition(aid,"FAILED_FORM",str(e))
            except Exception: update_application(aid,status="FAILED_FORM",notes=str(e))
            log_event(aid,"APPLICATION_ERROR",str(e)); raise
        finally: context.close()
