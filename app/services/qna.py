from pathlib import Path
import json,yaml
from ..db import save_qna
ROOT=Path(__file__).resolve().parents[2]

def seed_qna(profile=None):
    if profile is None:
        # Falls back to the public example profile when the real (personal, gitignored) one
        # hasn't been set up yet -- keeps a fresh clone runnable instead of crashing outright.
        path=ROOT/'config/profile.json'
        if not path.exists(): path=ROOT/'config/profile.example.json'
        profile=json.loads(path.read_text(encoding='utf-8'))
    p=profile
    def get(path):
        x=p
        for part in path.split('.'):
            if isinstance(x,dict): x=x.get(part,'')
            elif isinstance(x,list) and part.isdigit() and int(part)<len(x): x=x[int(part)]
            else: return ''
        if isinstance(x,(dict,list)): return json.dumps(x,ensure_ascii=False)
        return x
    data=yaml.safe_load((ROOT/'config/qna.yaml').read_text(encoding='utf-8'))
    n=0
    for q in data.get('questions',[]):
        ans=get(q.get('answer_key',''))
        if ans is not None and ans!='':
            if isinstance(ans,bool): ans = 'Yes' if ans else 'No'
            elif isinstance(ans,dict): ans = '; '.join(f"{k}: {v}" for k,v in ans.items())
            save_qna(q['question'],str(ans),0 if q.get('requires_review') else 1,q.get('category','CUSTOM')); n+=1
    return n
