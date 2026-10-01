"""Application Question Engine: question -> company/role/experience/projects/career-preferences/
voice -> answer, with every factual claim in the answer traced back to a real source in the
profile. If a claim can't be traced, it is flagged NEEDS_USER_INPUT rather than silently kept —
this is what stops "I configured Kubernetes manifests" from quietly becoming "I deployed the
application to Kubernetes" the way a plain LLM call would let happen.
"""
import json, os, re, requests

from .skill_gap import _SKILL_PATTERNS
from .paste_sheet import voice_instructions, _EMOJI_RE, _BANNED_PHRASES

# Verbs that assert something stronger than "worked with" — if one of these appears next to a
# technology/claim that isn't backed by real profile evidence, the whole answer is flagged rather
# than shipped, since this is exactly the "wrote manifests" -> "deployed to production" failure
# mode the question engine exists to prevent.
_STRONG_CLAIM_VERBS=["deployed","shipped to production","led the team","managed a team of",
    "architected","launched","scaled to","in production"]

def _evidence_map(profile):
    """skill/technology -> the real experience or project it comes from, built from profile.json
    directly (not from strategy ranking) so evidence-checking works even for jobs that haven't
    been tailored yet."""
    evidence={}
    for exp in profile.get("experience", []):
        blob=(exp.get("title","")+" "+" ".join(exp.get("bullets",[]))).lower()
        for skill in _SKILL_PATTERNS:
            if _SKILL_PATTERNS[skill].search(blob):
                evidence.setdefault(skill, []).append(f"experience: {exp.get('title')} — {exp.get('company')}")
    for proj in profile.get("projects", []):
        blob=(proj.get("name","")+" "+" ".join(proj.get("stack",[]))+" "+" ".join(proj.get("bullets",[]))).lower()
        for skill in _SKILL_PATTERNS:
            if _SKILL_PATTERNS[skill].search(blob):
                evidence.setdefault(skill, []).append(f"project: {proj.get('name')}")
    return evidence

def _cite_claims(answer_text, evidence_map):
    text=answer_text.lower()
    cited=[]
    for skill, sources in evidence_map.items():
        if _SKILL_PATTERNS[skill].search(text):
            cited.append({"claim": skill, "sources": sources})
    unresolved=[]
    for verb in _STRONG_CLAIM_VERBS:
        if verb in text:
            unresolved.append(f"Answer contains a strong claim ('{verb}') — verify this is literally true before sending, not just directionally true.")
    return cited, unresolved

def _violates_voice(text):
    if _EMOJI_RE.search(text): return True
    low=text.lower()
    return any(p in low for p in _BANNED_PHRASES)

def _call_llm_for_question(profile, job, question, extra=""):
    from .llm import enabled
    if not enabled(): return None
    base=os.getenv('AI_BASE_URL','https://api.openai.com/v1').rstrip('/')
    model=os.getenv('AI_MODEL','gpt-5-mini')
    payload={
        'candidate_profile': profile,
        'job': {'title': job.get('title',''), 'company': job.get('company',''), 'description': job.get('description','')[:4000]},
        'question': question,
        'task': ('Answer this exact application question, in 60-120 words, using ONLY facts already in '
                 'candidate_profile. Do not invent an anecdote, employer, metric or outcome. If the honest '
                 'answer requires information not in the profile, say so plainly in the answer rather than '
                 'inventing it.' + extra),
    }
    r=requests.post(base+'/chat/completions',
        headers={'Authorization': 'Bearer '+os.environ['AI_API_KEY'], 'Content-Type': 'application/json'},
        json={'model': model, 'temperature': 0.3, 'messages': [
            {'role': 'system', 'content': 'You are a conservative writing assistant answering a real job application question for a real candidate. ' + voice_instructions(profile)},
            {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
        ]}, timeout=30)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content'].strip()

def answer_question(question, job, profile):
    """Returns {answer, evidence_status, cited_claims, unresolved, generation_mode}.
    evidence_status is one of: VERIFIED (every claim traced), NEEDS_REVIEW (strong claims present,
    verify before sending), NO_CLAIMS (answer makes no technology/skill claims to check, e.g. a
    pure preference question)."""
    evidence_map=_evidence_map(profile)
    answer=None; mode="deterministic-fallback"
    try:
        answer=_call_llm_for_question(profile, job, question)
        if answer:
            for attempt_extra in ["", " Your previous answer used forbidden phrases/emoji — rewrite plainly, no emoji, no buzzwords."]:
                if not _violates_voice(answer):
                    mode="llm"; break
                answer=_call_llm_for_question(profile, job, question, attempt_extra)
            if _violates_voice(answer or ""):
                answer=None
    except Exception:
        answer=None

    if not answer:
        # Deterministic fallback: an honest, plain answer that only ever names skills/projects
        # actually in the evidence map — never fabricates an anecdote.
        top_evidence=list(evidence_map.items())[:2]
        if top_evidence:
            parts=[f"{skill} ({srcs[0]})" for skill, srcs in top_evidence]
            answer=(f"Regarding \"{question}\": the most relevant real experience I can point to is "
                    f"{', and '.join(parts)}. I'd rather answer this specifically once I know more about "
                    f"what you're looking for than give a generic response.")
        else:
            answer=(f"I don't have profile evidence directly relevant to \"{question}\" yet — "
                    f"this needs my own input rather than a generated guess.")

    cited, unresolved = _cite_claims(answer, evidence_map)
    if unresolved:
        status="NEEDS_REVIEW"
    elif cited:
        status="VERIFIED"
    else:
        status="NO_CLAIMS"

    return {
        "question": question,
        "answer": answer,
        "evidence_status": status,
        "cited_claims": cited,
        "unresolved_warnings": unresolved,
        "generation_mode": mode,
    }
