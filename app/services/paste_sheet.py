"""Paste-ready application packet: contact block, a short paste-into-a-textbox
cover note, and factual answers to the screening questions almost every
application form asks — all written in one voice (direct, literate, no
corporate filler) so the person can paste straight into a form and submit it
themselves. AI is optional; a deterministic, hand-written fallback in the same
voice is used when it is unavailable or fails, so this feature never breaks.

Same factuality discipline as tailor.py/llm.py: never invent an employer,
metric, skill or year that is not already in the candidate profile.
"""
import json, os, re, requests

_EMOJI_RE=re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002700-\U000027BF"
    "\U0001F900-\U0001F9FF"
    "]+", flags=re.UNICODE)
# Phrases the model tends to reach for despite instructions not to. Presence of any of these
# means the whole response is discarded (not edited — editing AI prose programmatically risks
# leaving broken grammar) and the deterministic fallback is used instead.
_BANNED_PHRASES=["passionate","excited","thrilled","leverage","synergy","dynamic","impactful",
    "vibrant","align with","aligns with","aligning with","journey","i am writing to express my interest"]

def _violates_voice(data):
    blob=" ".join(str(v) for v in data.values()).lower()
    if _EMOJI_RE.search(blob): return True
    return any(p in blob for p in _BANNED_PHRASES)

_DEFAULT_VOICE_INSTRUCTIONS=(
    "Voice: the register of a sharp, classically-read person who does not perform enthusiasm — "
    "plain words, exact claims, not one wasted adjective. Sentences should have weight and rhythm, "
    "the way good prose does, but never ornate or flowery for its own sake. This is conviction on "
    "the page, not marketing copy.\n"
    "Absolutely forbidden: emoji of any kind, exclamation points, the words 'passionate', "
    "'excited', 'thrilled', 'leverage', 'synergy', 'dynamic', 'impactful', 'vibrant', 'ecosystem' "
    "(unless the job posting itself uses it as a technical term), 'align(s)/aligning', 'journey', "
    "any sentence that starts with 'I am writing to express my interest', and any generic praise of "
    "the company that could be pasted into an application for a different company unchanged.\n"
    "Every sentence must be a specific, checkable claim about this candidate or this role — not a "
    "feeling. Where the candidate's experience is genuinely thin, say so plainly and let the honesty "
    "carry it, rather than inflating language to compensate. Never invent a fact, employer, skill, "
    "metric or year that is not already present in candidate_profile. Never open with the company's "
    "own slogan, an internal meme, or any borrowed phrase from the job posting — open with the "
    "candidate's own claim, in the candidate's own words."
)

def voice_instructions(profile):
    """Builds the voice/style instruction from the user's editable voice_profile in
    config/profile.json, rather than a hardcoded style — so changing the profile actually changes
    generated tone without touching code. Falls back to the built-in default when the profile
    section is missing/empty (e.g. an older profile.json)."""
    vp=profile.get("voice_profile")
    if not vp: return _DEFAULT_VOICE_INSTRUCTIONS
    tone=", ".join(vp.get("tone",[])) or "natural, direct, not corporate"
    avoid=", ".join(f"'{p}'" for p in vp.get("avoid_phrases",[]))
    prefer=", ".join(vp.get("prefer",[]))
    samples=vp.get("writing_samples") or []
    samples_block=(
        "Style evidence — the candidate's own real writing, to match the voice to (never invent a "
        "personality beyond what these actually show):\n" + "\n---\n".join(samples)
    ) if samples else ""
    return (
        f"Voice: {tone}. Every sentence must be a specific, checkable claim about this candidate or "
        f"this role — not a feeling. Where the candidate's experience is genuinely thin, say so "
        f"plainly rather than inflating language to compensate. Never invent a fact, employer, "
        f"skill, metric or year that is not already present in candidate_profile.\n"
        f"Absolutely forbidden phrases/style: {avoid or 'generic corporate/AI-sludge language'}, "
        f"emoji, exclamation points, any sentence that starts with 'I am writing to express my "
        f"interest', and any generic company praise that could be pasted into a different "
        f"application unchanged.\n"
        f"Prefer: {prefer or 'concrete examples, concise answers, honest uncertainty'}.\n"
        f"{samples_block}"
    )

# Backward-compat name used elsewhere in this module before it became profile-driven.
VOICE_INSTRUCTIONS=_DEFAULT_VOICE_INSTRUCTIONS

def _call_llm(profile, job, extra_instruction=""):
    base=os.getenv('AI_BASE_URL','https://api.openai.com/v1').rstrip('/')
    model=os.getenv('AI_MODEL','gpt-5-mini')
    prompt={
        'candidate_profile': profile,
        'job': {'title':job.get('title',''),'company':job.get('company',''),'description':job.get('description','')[:6000]},
        'task': (
            'Write a paste-ready application packet for this candidate applying to this job. '
            'Return JSON only with these exact keys: cover_note (140-200 words, a short paste-into-a-textarea '
            'cover note — not a full letter, not a summary of the resume, an actual case for why this specific '
            'person wants this specific role), why_this_role (2-3 sentences), greatest_strength (2-3 sentences, '
            'grounded in one real bullet from experience or projects), work_authorization_answer (1-2 sentences, '
            'factual, based on candidate_profile.candidate.work_authorization), notice_period_answer (1 sentence, '
            'based on candidate_profile.candidate.notice_period), salary_expectation_answer (1-2 sentences, based '
            'on candidate_profile.preferences.preferred_salary_eur, framed as flexible/negotiable).'
            + extra_instruction
        )
    }
    r=requests.post(base+'/chat/completions',headers={'Authorization':'Bearer '+os.environ['AI_API_KEY'],'Content-Type':'application/json'},
        json={'model':model,'temperature':0.3,'messages':[
            {'role':'system','content':'You are a conservative, literate writing assistant helping a real candidate apply for real jobs. '+voice_instructions(profile)},
            {'role':'user','content':json.dumps(prompt,ensure_ascii=False)}
        ]},timeout=30)
    r.raise_for_status(); content=r.json()['choices'][0]['message']['content']
    if '```' in content: content=content.split('```',1)[1].replace('json','',1).strip().rsplit('```',1)[0]
    return json.loads(content)

def _ai_paste_sheet(profile, job):
    from .llm import enabled
    if not enabled(): return None
    required=['cover_note','why_this_role','greatest_strength','work_authorization_answer','notice_period_answer','salary_expectation_answer']
    for attempt,extra in enumerate([
        "",
        " Your previous attempt used forbidden words or an emoji. Rewrite it cleanly: no emoji, no "
        "exclamation points, none of the forbidden words listed in the system instructions."
    ]):
        data=_call_llm(profile, job, extra)
        if not all(isinstance(data.get(k),str) and data.get(k).strip() for k in required): continue
        if not _violates_voice(data): return data
    return None

def _most_relevant(items, key_text_fn, job_text):
    """Rank facts (experience/projects) by keyword overlap with the job text, same idea as
    tailor.build_strategy, so the fallback voice talks about the *relevant* fact, not just item 0."""
    jt=set(w for w in job_text.lower().split() if len(w)>3)
    scored=[(len(jt & set(key_text_fn(x).lower().split())),x) for x in items]
    scored.sort(key=lambda t:-t[0])
    return scored[0][1] if scored else None

def _fallback_paste_sheet(profile, job):
    c=profile['candidate']; exp=profile.get('experience',[]); projs=profile.get('projects',[])
    job_text=(job.get('title','')+' '+job.get('description',''))
    top_exp=_most_relevant(exp, lambda e: e.get('title','')+' '+' '.join(e.get('bullets',[])), job_text)
    top_proj=_most_relevant(projs, lambda p: p.get('name','')+' '+' '.join(p.get('bullets',[])), job_text)
    title=job.get('title','this role'); company=job.get('company','your team')
    exp_line=f"At {top_exp.get('company','')}, {top_exp.get('bullets',[''])[0].rstrip('.')}." if top_exp else ""
    proj_line=f"Outside of that: {top_proj.get('name','')} — {top_proj.get('bullets',[''])[0].rstrip('.')}." if top_proj else ""
    strength_bits=[b for b in (exp_line,proj_line) if b]
    greatest_strength=" ".join(strength_bits) or "I finish what I start, and I check my own work before anyone else has to."
    cover_note=(
        f"I am applying for {title} at {company}. Plainly: the work described is close to what I already do, "
        f"not what I am hoping to grow into. {exp_line} "
        f"I do not have years behind me — I have real, checkable work instead, and the attention to do it "
        f"properly. I would rather understate what I can do than perform confidence I have not yet earned. "
        f"If that is useful to your team, I am glad to talk further."
    ).strip()
    return {
        'cover_note': cover_note,
        'why_this_role': f"The scope of {title} sits close to what I already build and study; I am not reaching for a title, I am asking for the room to do the work well.",
        'greatest_strength': greatest_strength,
        'work_authorization_answer': c.get('work_authorization',''),
        'notice_period_answer': c.get('notice_period',''),
        'salary_expectation_answer': f"Open and negotiable; roughly EUR {profile.get('preferences',{}).get('preferred_salary_eur','')} as a starting reference point, adjustable to scope and location.",
    }

def generate_paste_sheet(profile, job):
    try:
        data=_ai_paste_sheet(profile, job)
        if data: return data, 'llm'
    except Exception:
        pass
    return _fallback_paste_sheet(profile, job), 'deterministic-fallback'

def _as_text(profile, job, data):
    c=profile['candidate']
    return (
        f"{c.get('name','')}\n{c.get('email','')} · {c.get('phone','')} · {c.get('city','')} · {c.get('linkedin','')}\n"
        f"Applying for: {job.get('title','')} at {job.get('company','')}\n\n"
        f"— COVER NOTE (paste into the cover letter / message box) —\n{data['cover_note']}\n\n"
        f"— WHY THIS ROLE —\n{data['why_this_role']}\n\n"
        f"— GREATEST STRENGTH —\n{data['greatest_strength']}\n\n"
        f"— WORK AUTHORIZATION —\n{data['work_authorization_answer']}\n\n"
        f"— NOTICE PERIOD —\n{data['notice_period_answer']}\n\n"
        f"— SALARY EXPECTATION —\n{data['salary_expectation_answer']}\n"
    )

def build_and_save_paste_sheet(job_id):
    from pathlib import Path
    from ..db import create_application, get_job
    from .tailor import ROOT, load_profile
    job=get_job(job_id)
    if not job: raise ValueError("Unknown job")
    profile=load_profile(); aid=create_application(job_id)
    data,mode=generate_paste_sheet(profile,job)
    out=ROOT/"data/applications"/aid/"paste_sheet"; out.mkdir(parents=True,exist_ok=True)
    (out/"paste_sheet.json").write_text(json.dumps({**data,"generation_mode":mode},indent=2,ensure_ascii=False),encoding="utf-8")
    (out/"paste_sheet.txt").write_text(_as_text(profile,job,data),encoding="utf-8")
    return aid, data, mode

def load_saved_paste_sheet(aid):
    from .tailor import ROOT
    p=ROOT/"data/applications"/aid/"paste_sheet"/"paste_sheet.json"
    if not p.exists(): return None
    return json.loads(p.read_text(encoding="utf-8"))
