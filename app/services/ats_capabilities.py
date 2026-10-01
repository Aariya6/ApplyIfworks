from dataclasses import dataclass,asdict
@dataclass(frozen=True)
class Capability:
    discover:bool; jd:bool; application_url:bool; open_application:bool; fill_fields:bool; uploads:bool; screening:bool; safe_answers:bool; human_gate:bool; submit:bool; verify:bool; evidence:bool; status:str
    def to_dict(self): return asdict(self)
# v3 only marks a capability TRUE when the code path exists; submit/verify remain REVIEW until an ATS-specific fixture proves them.
DIRECT=Capability(True,True,True,True,True,True,True,True,True,False,False,True,'PARTIAL')
DISCOVERY_ONLY=Capability(True,True,True,True,True,True,True,True,True,False,False,True,'REVIEW')
ATS_CAPABILITIES={k:DIRECT for k in ['greenhouse','lever','ashby','workable','smartrecruiters','personio']}
ATS_CAPABILITIES.update({k:DISCOVERY_ONLY for k in ['teamtailor','recruitee','workday','icims','successfactors','taleo','unknown']})
def capabilities(ats): return ATS_CAPABILITIES.get((ats or 'unknown').lower(),DISCOVERY_ONLY).to_dict()
