import re,json
from ..db import add_screening_question,get_qna
CATS={
 "WORK_AUTHORIZATION":["authorized to work","legally authorized","right to work","work authorization"],
 "VISA":["visa sponsorship","require sponsorship","sponsor a visa","visa"],
 "SALARY":["salary expectation","expected salary","compensation"],
 "AVAILABILITY":["start date","available to start","notice period"],
 "LOCATION":["current location","located in","willing to relocate","relocate"],
 "EDUCATION":["university","degree","graduation"],
 "EXPERIENCE":["years of experience","professional experience","years' experience"],
 "SKILL":["experience with","proficiency in","how many years"],
 "LANGUAGE":["language","german level","english level"],
 "DEMOGRAPHIC":["gender","ethnicity","race","veteran","disability"],
}
def classify(q):
    t=q.lower()
    for c,terms in CATS.items():
        if any(x in t for x in terms): return c
    return "CUSTOM"
def approved_answer(question,profile):
    stored=get_qna(question)
    if stored and stored.get("approved") and stored.get("answer"):
        return stored["answer"],1.0
    q=question.lower(); c=profile["candidate"]
    if "university" in q: return c.get("university"),1.0
    if "degree" in q: return c.get("degree"),1.0
    if "email" in q:return c.get("email"),1.0
    if "phone" in q:return c.get("phone"),1.0
    if "linkedin" in q:return c.get("linkedin"),1.0
    if "german" in q:return c.get("languages",{}).get("German"),0.98
    if "english" in q:return c.get("languages",{}).get("English"),0.98
    return None,0.0
def analyze_questions(aid,questions,profile):
    out=[]
    for q in questions:
        cat=classify(q); ans,conf=approved_answer(q,profile)
        if cat in {"WORK_AUTHORIZATION","VISA","SALARY","DEMOGRAPHIC","CUSTOM"}: ans=None; conf=0
        status="AUTO_ANSWER" if ans is not None and conf>=0.95 else "REQUIRES_HUMAN"
        add_screening_question(aid,q,cat,conf,ans or "",status)
        out.append({"question":q,"category":cat,"answer":ans,"confidence":conf,"status":status})
    return out
