"""Job intelligence: work authorization, salary normalization and eligibility signals."""
import re
from dataclasses import dataclass, asdict

COUNTRY_ALIASES={
    'germany':['germany','deutschland','berlin','munich','münchen','hamburg','frankfurt','cologne','köln'],
    'netherlands':['netherlands','the netherlands','amsterdam','rotterdam'],
    'austria':['austria','vienna','wien'], 'belgium':['belgium','brussels'],
    'switzerland':['switzerland','zurich','zürich','geneva','lausanne'],
    'france':['france','paris'], 'ireland':['ireland','dublin'],
    'spain':['spain','madrid','barcelona'], 'finland':['finland','helsinki'],
    'sweden':['sweden','stockholm'], 'denmark':['denmark','copenhagen'],
    'norway':['norway','oslo'], 'poland':['poland','warsaw','krakow','kraków'],
    'czechia':['czechia','czech republic','prague'],
    'united kingdom':['united kingdom','uk','u.k.','england','london','manchester','edinburgh','scotland','wales'],
    'estonia':['estonia','tallinn'], 'singapore':['singapore'],
    'europe':['europe','european union','eu','emea'],
    # Not targets, but must be recognized so a job clearly located here isn't silently
    # miscategorized as "unknown" (and therefore let through with no country penalty).
    'united states':['united states','usa','u.s.a.','u.s.','us only','new york','san francisco',
        'california','texas','seattle','austin, tx','boston, ma','chicago, il','remote - usa','remote, usa','remote (usa)'],
    'canada':['canada','toronto','vancouver','montreal'],
    'australia':['australia','sydney','melbourne'],
    'india':['india','bangalore','bengaluru','hyderabad','mumbai','pune','delhi'],
    'brazil':['brazil','são paulo','sao paulo'], 'mexico':['mexico','mexico city'],
    'japan':['japan','tokyo'], 'south africa':['south africa'], 'new zealand':['new zealand'],
}
NON_EU_TARGET={'switzerland','united kingdom','singapore','norway','estonia'}
EU_TARGET={'germany','netherlands','austria','belgium','france','ireland','spain','finland','sweden','denmark','poland','czechia'}
# Countries we can confidently detect but never want to rank highly for this candidate: no
# EOR/worldwide-remote signal rescues these, since "prefer only Europe" was explicit.
NON_TARGET_COUNTRIES={'united states','canada','australia','brazil','mexico','japan','south africa','new zealand'}
@dataclass
class Salary:
    raw:str=''; currency:str=''; minimum:float|None=None; maximum:float|None=None; period:str='unknown'; confidence:float=0.0
    def to_dict(self): return asdict(self)

def extract_salary(text):
    t=' '.join(text.split())
    if not t: return Salary()
    currency=''
    for symbol,code in [('€','EUR'),('$','USD'),('£','GBP'),('CHF','CHF')]:
        if symbol in t or code.lower() in t.lower(): currency=code; break
    m=re.search(r'(?:€|\$|£|CHF|EUR|USD|GBP)\s*(\d[\d,.]*)\s*(k|K)?\s*(?:[-–]\s*(?:€|\$|£|CHF|EUR|USD|GBP)?\s*(\d[\d,.]*)\s*(k|K)?)?',t)
    if not m: m=re.search(r'(\d[\d,.]*)\s*(?:-|–)\s*(\d[\d,.]*)\s*(k|K)?\s*(EUR|USD|GBP|CHF)',t)
    if not m:
        return Salary(raw=t,currency=currency,confidence=0.25 if any(x in t.lower() for x in ['salary','compensation','pay']) else 0)
    try:
        g=m.groups(); nums=[float(g[0].replace(',',''))*(1000 if g[1] else 1)]
        if len(g)>2 and g[2]: nums.append(float(g[2].replace(',',''))*(1000 if g[3] else 1))
    except ValueError:
        return Salary(raw=t,currency=currency,confidence=0.25 if any(x in t.lower() for x in ['salary','compensation','pay']) else 0)
    period='hourly' if re.search(r'/(?:hour|hr)|per hour',t,re.I) else 'annual' if re.search(r'(?:year|annum|p\.a\.)',t,re.I) else 'unknown'
    return Salary(raw=m.group(0),currency=currency,minimum=nums[0] if nums else None,maximum=nums[1] if len(nums)>1 else (nums[0] if nums else None),period=period,confidence=0.95)

# Citizenship/work-authorization language for a specific country, independent of where the
# company happens to be headquartered. This is the actual legal blocker a candidate cares about,
# not "the office is in the US" (many US companies do hire EU-based remote contractors).
_CITIZENSHIP_RE=re.compile(
    r'(?:must\s+(?:be\s+)?(?:a\s+)?|require[sd]?\s+|only\s+)?'
    r'(us|u\.s\.|united states|american)\s+citizen(?:ship)?'
    r'|authoriz(?:ed|ation)\s+to\s+work\s+in\s+the\s+(?:us|u\.s\.|united states)(?:\s+without\s+sponsorship)?'
    r'|(?:must\s+have\s+)?(?:a\s+)?green\s?card'
    r'|no\s+sponsorship\s+(?:available|provided|offered)',
    re.I)

def work_auth(text, location=''):
    t=(text+' '+location).lower()
    if _CITIZENSHIP_RE.search(t): return 'US_CITIZENSHIP_REQUIRED'
    if any(x in t for x in ['worldwide','work from anywhere','anywhere in the world','global remote']): return 'REMOTE_WORLDWIDE'
    if any(x in t for x in ['contractor worldwide','international contractors','contractor globally']): return 'CONTRACTOR_SUPPORTED'
    if any(x in t for x in ['employer of record','eor','remote.com','deel']) and any(x in t for x in ['india','international','global']): return 'EOR_SUPPORTED'
    if re.search(r'\b(eu|european union)\s*(citizens|citizenship|work authorization|right to work)',t): return 'EU_ONLY'
    if any(x in t for x in ['must be based in','based in germany','located in germany','germany only']): return 'COUNTRY_RESTRICTED'
    if any(x in t for x in ['remote europe','remote in europe','europe only']): return 'REMOTE_EUROPE'
    if 'remote germany' in t or 'remote - germany' in t: return 'REMOTE_GERMANY'
    if 'remote eu' in t: return 'REMOTE_EU'
    return 'UNKNOWN'

def eligibility_for_india(auth):
    return {'REMOTE_WORLDWIDE':'eligible','CONTRACTOR_SUPPORTED':'contractor_possible','EOR_SUPPORTED':'eor_supported','REMOTE_EUROPE':'probably_ineligible_without_local_work_rights','REMOTE_EU':'probably_ineligible_without_local_work_rights','REMOTE_GERMANY':'probably_ineligible_without_local_work_rights','EU_ONLY':'probably_ineligible_without_local_work_rights','COUNTRY_RESTRICTED':'human_review','US_CITIZENSHIP_REQUIRED':'ineligible','UNKNOWN':'human_review'}.get(auth,'human_review')


# "US"/"USA" as a bare 2-3 letter country-code token only ever means something reliable when it's
# capitalized the way location/title fields conventionally write it ("US Remote", "Remote - US").
# Lowercase "us" is overwhelmingly the pronoun ("join us", "about us") and must never be matched.
_US_TOKEN_RE=re.compile(r'\bUS\b|\bUSA\b')

def infer_country(text, location=''):
    """Prefer the job's actual location field and title — far cleaner signals than scanning the
    whole description, which routinely mentions unrelated countries ("clients across Europe",
    "offices in the UK and Spain") that have nothing to do with where this specific role sits."""
    raw_location=str(location or ''); raw_text=str(text or '')
    if _US_TOKEN_RE.search(raw_location) or _US_TOKEN_RE.search(raw_text[:120]): return 'united states'
    loc=raw_location.lower()
    if loc:
        for country, aliases in COUNTRY_ALIASES.items():
            if any(re.search(r'\b'+re.escape(a)+r'\b',loc) for a in aliases): return country
        if any(x in loc for x in ['worldwide','anywhere','global']): return 'global'
    t=(raw_text+' '+loc).lower()
    for country, aliases in COUNTRY_ALIASES.items():
        if any(re.search(r'\b'+re.escape(a)+r'\b',t) for a in aliases): return country
    if 'remote worldwide' in t or 'global remote' in t: return 'global'
    return 'unknown'

def country_fit(country, preferences):
    targets=[str(x).lower() for x in preferences.get('target_countries',[])]
    if country in NON_TARGET_COUNTRIES: return 'excluded'
    if not targets or country=='unknown': return 'unknown'
    if country in targets or country=='global': return 'target'
    return 'other'
