import re, datetime
from rapidfuzz import fuzz
from .job_intelligence import work_auth,eligibility_for_india,extract_salary,infer_country,country_fit as _country_fit
ROLE_FAMILIES={
 # --- Core technical (candidate is directly qualified for these) ---
 "AI_ENGINEERING":["ai engineer","machine learning engineer","ml engineer","applied ai","llm engineer","research engineer","nlp engineer","computer vision","ai research engineer"],
 "MLOPS_PLATFORM":["mlops","platform engineer","cloud engineer","site reliability","devops engineer","infrastructure engineer","sre "],
 "DATA": ["data engineer","data scientist","analytics engineer","machine learning"],
 "SOFTWARE": ["software engineer","backend engineer","python engineer","full stack","full-stack","platform engineer"],
 # --- AI-flavored product/business hybrid (checked before generic PM so "AI Product Manager"
 # lands here, not in plain PRODUCT_MANAGEMENT) ---
 "AI_PRODUCT":["ai product","ai program","technical program","technical product manager","ai product manager"],
 # --- Product/business hybrid: transferable via leadership + technical grounding, not directly
 # qualified the way an engineering title is ---
 "PRODUCT_MANAGEMENT":["product manager","product owner","associate product manager","product analyst","product operations"],
 "PROGRAM_MANAGEMENT":["program manager","project manager","technical project manager","program/operations","project/operations"],
 "CONSULTING_SOLUTIONS":["solutions engineer","solutions architect","business analyst","technology consultant","ai consultant","innovation consultant"],
 # --- Communication/community/leadership: transferable via TEDx, MLSA, workshops, mentoring ---
 "DEVELOPER_RELATIONS":["developer relations","developer advocate","technical evangelist","developer experience","community engineer","developer community"],
 "TECHNICAL_COMMUNICATION":["technical writer","developer documentation","technical communicator","technical education","ai trainer","ai education"],
 "COMMUNITY_OPERATIONS":["community manager","partnerships","ecosystem manager","event manager","program coordinator","business operations","strategy & operations","strategy and operations"],
 "AI_HUMANITIES":["ai policy","responsible ai","ai ethics","ai governance","digital humanities","humanities","research assistant",
    "computational humanities","cultural analytics","cultural data science","cultural data","ai for archives","digital archives",
    "museum technology","computational linguistics"],
 # --- Music/audio + software/AI: genuinely technical engineering roles (MIR, audio ML, music
 # NLP/generative), scored as core tech since real AI/software skills directly apply. Added
 # per the candidate's explicit request to search these intersections without narrowing the
 # existing search. ---
 "MUSIC_TECH_ENGINEERING":["music-tech","music tech","audio ai","audio ml","ai music","music ai","audio engineer machine learning","music information retrieval",
    "mir engineer","generative music","music generation","lyrics ai","ai lyrics","music nlp","music-language ai","music language ai",
    "computational creativity","music data engineer","music data scientist","streaming technology engineer",
    "digital signal processing engineer","dsp engineer","audio technology engineer"],
 # --- Music/audio product, strategy and platform roles: transferable via product/business
 # grounding, not a direct engineering-title match. ---
 "MUSIC_TECH_PRODUCT":["music product","music-tech product","artist technology","artist innovation","music industry technology",
    "audience intelligence","streaming platform product","digital music platform","artist platform","royalties technology",
    "rights technology","creator tools product","fan engagement technology","music discovery product"],
 # --- Creative technology / generative media, adjacent to but distinct from music-tech: also
 # core-tech, since these require real software/AI engineering skill, not just "creative" framing. ---
 "CREATIVE_TECHNOLOGY":["creative technologist","creative ai engineer","generative media engineer","interactive experience engineer",
    "ai artist tools","audiovisual technology engineer","computational creativity researcher","creative technology r&d",
    "emerging technology entertainment","interactive media technologist"],
 # A deliberately separate, exploratory track (see fit_tier): a CSE degree does not qualify
 # someone for these on its own, so this family is never scored on the normal
 # QUALIFIED/TRANSFERABLE/STRETCH ladder — see humanities_eligibility.py for its own 6-tier scale.
 "HUMANITIES_LITERATURE":["literary","editorial","publishing","cultural research","humanities ai evaluation",
    "content research","arts and culture","arts & culture","literary ai training","literature","copyediting","proofreading",
    "literary ai","literary technology","poetry ai","narrative ai research","literature nlp"],
}
CORE_TECH_FAMILIES={"AI_ENGINEERING","MLOPS_PLATFORM","DATA","SOFTWARE","MUSIC_TECH_ENGINEERING","CREATIVE_TECHNOLOGY"}
TRANSFERABLE_FAMILIES={"AI_PRODUCT","PRODUCT_MANAGEMENT","PROGRAM_MANAGEMENT","CONSULTING_SOLUTIONS","DEVELOPER_RELATIONS","TECHNICAL_COMMUNICATION","COMMUNITY_OPERATIONS","AI_HUMANITIES","MUSIC_TECH_PRODUCT"}
SALES_NEG=["sales","account executive","business development","bdr","sdr","cold calling","commission","telemarketing","outbound sales"]
# Founder/executive listings (often equity-stake or co-founder search posts, not an employment
# role we can apply to at all) — hard-excluded like sales, not just penalized.
FOUNDER_NEG=["co-founder","cofounder","founder","ceo","cto","cfo","coo","chief executive officer"]
# Titles that unambiguously require years of prior professional leadership/seniority we don't have.
SENIOR_TITLE_NEG=["senior","staff","principal","director","head of"," vp ","vp,","vice president","chief","architect","president"]
# Titles that *often* need people-management experience but sometimes hide an entry-level role
# (e.g. "Associate Product Manager"); penalized hard but not fully excluded.
LEAD_MANAGER_TITLE_NEG=["lead ","team lead"," lead,"," lead."," lead"," manager","engineering manager"]
YEARS_REQUIRED_RE=re.compile(r'(\d{1,2})\s*\+?\s*(?:to|-|–)?\s*\d{0,2}\s*\+?\s*years?\s*(?:of\s+)?(?:relevant\s+|professional\s+|proven\s+|hands-?on\s+|prior\s+)?experience', re.I)

def required_years(text):
    """Best-effort minimum years-of-experience requirement mentioned in a JD. None if not stated."""
    m=YEARS_REQUIRED_RE.search(text or "")
    return int(m.group(1)) if m else None

def days_since_posted(posted_at):
    if not posted_at: return None
    try:
        if posted_at.strip().isdigit():
            dt=datetime.datetime.fromtimestamp(int(posted_at),tz=datetime.timezone.utc)
        else:
            dt=datetime.datetime.fromisoformat(posted_at.replace('Z','+00:00'))
            if dt.tzinfo is None: dt=dt.replace(tzinfo=datetime.timezone.utc)
        return (datetime.datetime.now(datetime.timezone.utc)-dt).days
    except Exception:
        return None

def role_family(title,desc=""):
    text=(title+" "+desc).lower()
    for family,terms in ROLE_FAMILIES.items():
        if any(t in text for t in terms): return family
    return "OTHER_TECH"

def remote_state(job):
    text=" ".join(str(job.get(k,"")) for k in ["remote","location","description"]).lower()
    if any(x in text for x in ["remote europe","remote eu","european union","work from anywhere"]): return "remote_europe"
    if "remote" in text or job.get("remote")=="remote": return "remote"
    return "unknown"

def application_friction(job):
    ats=(job.get("ats") or "").lower(); d=(job.get("description") or "").lower()
    if ats in {"greenhouse","lever","ashby","workable","smartrecruiters","personio","teamtailor","recruitee"}: return "low"
    if ats in {"workday","icims","successfactors","taleo"}: return "high"
    if any(x in d for x in ["create an account","login required","multiple assessments"]): return "high"
    return "medium"

def score_job(job,profile):
    p=profile["preferences"];
    if str(job.get("title","")).upper() == "CAREERS_PAGE": return 0,["company career page watch target, not a job listing"],"CAREERS_PAGE","medium"
    text=(job.get("title","")+" "+job.get("description","")+" "+job.get("location","")).lower(); title=job.get("title","").lower()
    if any(x in text for x in p.get("exclude_titles",[])+SALES_NEG): return 0,["excluded sales/business-development role"],"EXCLUDED",application_friction(job)
    padded_title_pre=f" {title} "
    if any(x in padded_title_pre for x in FOUNDER_NEG): return 0,["excluded: founder/executive listing, not an employment role"],"EXCLUDED",application_friction(job)
    max_years=p.get("max_years_experience")
    if max_years is not None:
        req=required_years(job.get("description",""))
        if req is not None and req>max_years+1:
            return 0,[f"excluded: requires {req}+ years experience (candidate max {max_years})"],"EXCLUDED",application_friction(job)
    # Geography: computed here directly rather than trusted from the job dict, because during
    # discovery those fields aren't populated on the record until *after* scoring runs.
    wa=work_auth(job.get("description",""),job.get("location",""))
    if wa=="US_CITIZENSHIP_REQUIRED": return 0,["excluded: requires US citizenship/work authorization"],"EXCLUDED",application_friction(job)
    country=infer_country(job.get("title","")+" "+job.get("description",""),job.get("location",""))
    cfit=_country_fit(country,p)
    if cfit=="excluded" and wa not in {"REMOTE_WORLDWIDE","CONTRACTOR_SUPPORTED","EOR_SUPPORTED"}:
        return 0,[f"excluded: located in {country}, outside target countries, no worldwide/EOR remote signal"],"EXCLUDED",application_friction(job)
    score=0; reasons=[]
    family=role_family(job.get("title",""),job.get("description",""))
    if family in CORE_TECH_FAMILIES: score+=14; reasons.append(f"role-family:{family}(qualified)")
    elif family in TRANSFERABLE_FAMILIES: score+=8; reasons.append(f"role-family:{family}(transferable)")
    for pref in p.get("preferred_domains",[]):
        if pref.lower() in text: score+=4; reasons.append(f"domain:{pref}")
    skill_blob=" ".join(sum(profile.get("skills",{}).values(),[])).lower()
    matched=sum(1 for s in sum(profile.get("skills",{}).values(),[]) if s.lower() in text)
    score+=min(25,matched*2)
    rs=remote_state(job)
    if rs in {"remote","remote_europe"}: score+=18; reasons.append("remote")
    if any(x.lower() in text for x in p.get("regions",[])): score+=8; reasons.append("target-region")
    if cfit == "target": score += 7; reasons.append("target-country")
    if any(x in text for x in ["hybrid", "on-site", "onsite"]): score -= 12; reasons.append("non-remote-signal")
    padded_title=f" {title} "
    if any(x in padded_title for x in SENIOR_TITLE_NEG): score-=45; reasons.append("seniority-risk:title")
    elif any(x in padded_title for x in LEAD_MANAGER_TITLE_NEG): score-=25; reasons.append("seniority-risk:lead-or-manager-title")
    if any(x in title for x in ["intern","working student","werkstudent"]): score-=8; reasons.append("not-target-full-time")
    if "full-time" in (job.get("employment") or "").lower() or "full time" in text: score+=7; reasons.append("full-time")
    if any(x in text for x in ["english", "english-speaking", "english language"]): score+=4; reasons.append("english-signal")
    req=required_years(job.get("description",""))
    if req is not None and max_years is not None and req>max_years: score-=15; reasons.append(f"experience-gap:{req}y-required")
    age=days_since_posted(job.get("posted_at"))
    if age is not None:
        if age<=3: score+=10; reasons.append("posted:last-3-days")
        elif age<=7: score+=6; reasons.append("posted:last-week")
        elif age<=14: score+=3; reasons.append("posted:last-2-weeks")
        elif age>60: score-=8; reasons.append("posted:stale")
    friction=application_friction(job)
    if friction=="low": score+=5; reasons.append("low-application-friction")
    if friction=="high": score-=3; reasons.append("high-application-friction")
    if any(x in text for x in ["german required","fluent german","german language required"]): score-=8; reasons.append("german-required")
    return max(0,min(100,score)),reasons,family,friction

def fit_tier(score,family,reasons):
    """Four-way classification, computed from the already-scored signal rather than a second
    parallel system: QUALIFIED (core technical fit), TRANSFERABLE (leadership/communication/
    product-adjacent, credible via real experience but not a direct technical match), STRETCH
    (right family, but an experience or seniority gap flagged it), MISMATCH (everything else —
    including jobs that hit keyword overlaps but aren't a credible fit), EXCLUDED (hard filter)."""
    if score<=0 or family=="EXCLUDED" or family=="CAREERS_PAGE": return "EXCLUDED"
    if family=="HUMANITIES_LITERATURE": return "EXPLORATORY"
    has_gap=any(r.startswith("experience-gap") or r=="seniority-risk:title" or r=="seniority-risk:lead-or-manager-title" for r in reasons)
    if family in CORE_TECH_FAMILIES:
        if has_gap: return "STRETCH"
        if score>=55: return "QUALIFIED"
        if score>=30: return "STRETCH"
        return "MISMATCH"
    if family in TRANSFERABLE_FAMILIES:
        if score>=45 and not has_gap: return "TRANSFERABLE"
        if score>=25: return "STRETCH"
        return "MISMATCH"
    return "MISMATCH"
