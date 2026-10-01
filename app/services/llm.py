import os, json, requests

def enabled():
    return bool(os.getenv('AI_API_KEY'))

def generate_strategy(profile, job, fallback):
    if not enabled(): return fallback, 'deterministic-fallback'
    base=os.getenv('AI_BASE_URL','https://api.openai.com/v1').rstrip('/')
    model=os.getenv('AI_MODEL','gpt-5-mini')
    prompt={
      'candidate_profile': profile,
      'job': {'title':job.get('title',''),'company':job.get('company',''),'description':job.get('description','')},
      'task':(
        'Create a resume tailoring strategy. Do not invent facts. Return JSON only with role_family, '
        'priority_skills, priority_experience_names, priority_project_names, keywords_supported, '
        'keywords_missing, claims_forbidden, tailored_summary. Every supported claim must be directly '
        'present in candidate_profile.\n'
        'tailored_summary: 1-2 sentences for the top of the résumé, specific to THIS job and company — '
        'not a generic summary that could be reused for any role in the same field. It must name what in '
        'candidate_profile actually connects to what this JD is asking for (a real skill, project or '
        'experience bullet), using only facts already in candidate_profile. No invented metrics, no '
        'company names other than ones already in candidate_profile, no claim of years of experience the '
        'candidate does not have.'
      )
    }
    r=requests.post(base+'/chat/completions',headers={'Authorization':'Bearer '+os.environ['AI_API_KEY'],'Content-Type':'application/json'},json={'model':model,'temperature':0,'messages':[{'role':'system','content':'You are a conservative resume tailoring engine. Never invent experience, metrics, employers, skills or years.'},{'role':'user','content':json.dumps(prompt,ensure_ascii=False)}]},timeout=30)
    r.raise_for_status(); content=r.json()['choices'][0]['message']['content']
    if '```' in content: content=content.split('```',1)[1].replace('json','',1).strip().rsplit('```',1)[0]
    data=json.loads(content)
    allowed_exp={e['title']:e for e in profile.get('experience',[])}; allowed_proj={p['name']:p for p in profile.get('projects',[])}; facts=json.dumps(profile).lower()
    data['priority_experience']=[allowed_exp[x] for x in data.get('priority_experience_names',[]) if x in allowed_exp]
    data['priority_projects']=[allowed_proj[x] for x in data.get('priority_project_names',[]) if x in allowed_proj]
    data['priority_skills']=[x for x in data.get('priority_skills',[]) if x.lower() in facts]
    data['keywords_supported']=[x for x in data.get('keywords_supported',[]) if x.lower() in facts]
    data['keywords_missing']=[x for x in data.get('keywords_missing',[]) if x.lower() not in facts]
    data['claims_forbidden']=[x for x in data.get('claims_forbidden',[]) if x.lower() not in facts]
    data.pop('priority_experience_names',None); data.pop('priority_project_names',None)
    # role_family drives a hard-coded lookup downstream and must stay a known,
    # deterministically-computed string; never trust the model's shape/value for it.
    data.pop('role_family',None)
    ts=data.get('tailored_summary')
    if not isinstance(ts,str) or not (20<len(ts.strip())<600): data.pop('tailored_summary',None)
    return {**fallback,**data}, 'llm'
