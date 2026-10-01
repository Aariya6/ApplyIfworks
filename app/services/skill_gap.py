"""Skill-gap analysis: looks at every job the candidate is actually a credible fit for
(QUALIFIED/TRANSFERABLE/STRETCH — never MISMATCH/EXCLUDED, since a term missing from a job
that's a bad fit anyway tells us nothing), checks which specific named technologies/skills the
JD asks for, and surfaces which ones recur most often across that pool but aren't yet in the
candidate's profile. This is the evidence a portfolio-project recommendation should be built on,
not a free-text keyword frequency count (which mostly surfaces filler words like "team"/"looking").
"""
import json, re
from collections import Counter

# A curated technology/skill vocabulary, not a free-text extractor — this is what makes the
# signal actually mean something (matches named tools, not generic English words). Grouped by
# area only for readability; matching is flat across all of them.
SKILL_TAXONOMY=[
    # Languages
    "python","typescript","javascript","java","go","golang","rust","c++","c#","kotlin","swift","scala","ruby","php",
    # AI/ML
    "pytorch","tensorflow","scikit-learn","huggingface","transformers","llm","llms","langchain","llamaindex",
    "rag","nlp","computer vision","reinforcement learning","fine-tuning","prompt engineering","openai api",
    "anthropic api","vector database","embeddings","mlops","kubeflow","mlflow","airflow",
    # Web/frameworks
    "react","next.js","vue","angular","svelte","node.js","express","django","flask","fastapi","spring boot",
    "graphql","rest api","grpc","tailwind",
    # Data/DBs
    "postgresql","mysql","mongodb","redis","elasticsearch","graph database","neo4j","snowflake","bigquery",
    "spark","kafka","dbt","airbyte",
    # Cloud/infra
    "aws","azure","gcp","kubernetes","docker","terraform","ci/cd","github actions","jenkins",
    # Product/PM tooling
    "jira","figma","amplitude","mixpanel","sql","a/b testing","roadmapping","agile","scrum",
    # General CS
    "microservices","distributed systems","system design","unit testing","tdd","websockets",
]

def _norm(text): return (text or "").lower()

# Word-boundary regex per skill, compiled once. Plain substring matching would false-positive
# badly here — "rag" inside "average/storage/leverage", "go" inside "going/good", etc.
_SKILL_PATTERNS={s: re.compile(r'(?<![a-z0-9])'+re.escape(s)+r'(?![a-z0-9])') for s in SKILL_TAXONOMY}

def compute_skill_gaps(top_n=25):
    from ..db import jobs
    from .tailor import load_profile
    profile=load_profile()
    facts=_norm(json.dumps(profile))
    js=[j for j in jobs(10000) if (j.get("fit_tier") or "MISMATCH") in {"QUALIFIED","TRANSFERABLE","STRETCH"}]
    counter=Counter(); examples={}
    for j in js:
        text=_norm(j.get("title","")+" "+(j.get("description","") or ""))
        for skill,pat in _SKILL_PATTERNS.items():
            if skill in facts: continue
            if pat.search(text):
                counter[skill]+=1
                examples.setdefault(skill,[]).append(j["id"])
    signals=[{"skill":k,"job_count":n,"example_job_ids":examples[k][:5]} for k,n in counter.most_common(top_n) if n>=3]
    return signals, len(js)

def recommend_project_focus(signals):
    """Turn the top recurring gaps into a plain-language recommendation, grounded only in the
    counted evidence — never a fabricated 'you should learn X' without the job-count behind it."""
    if not signals: return "Not enough high-fit jobs analyzed yet to surface a reliable pattern, or your profile already covers what they ask for."
    top=signals[:6]
    skills=", ".join(f"{s['skill']} ({s['job_count']})" for s in top)
    return (f"Across the jobs you're actually a credible fit for, these named technologies/skills recur "
            f"most and aren't yet reflected in your profile (count = number of matching jobs mentioning it): "
            f"{skills}. That's the evidence a next portfolio project should be built to demonstrate — "
            f"not a guess.")
