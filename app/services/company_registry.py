from pathlib import Path
import csv,re,datetime
from ..db import upsert_company
ROOT=Path(__file__).resolve().parents[2]

def _seed_file(path, default_country="", default_regions="Europe"):
    n=0
    with open(path,encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name=(r.get("company") or r.get("name") or "").strip()
            if not name: continue
            website=(r.get("website") or "").strip()
            cid=re.sub(r"[^a-z0-9]+","-",name.lower()).strip("-") or name.lower()
            country=(r.get("country") or default_country or "Global").strip()
            sector=(r.get("sector") or "technology").strip()
            remote=(r.get("remote_signal") or r.get("remote_note") or "").strip()
            upsert_company(id=cid,name=name,website=website,domain=website.split('//')[-1].split('/')[0].split('/')[0],city=r.get("city",""),country=country,remote_policy=remote,hiring_regions=r.get("hiring_regions",default_regions),discovered_from=path.name,last_checked=datetime.datetime.now(datetime.timezone.utc).isoformat(),status="SEEDED",sector=sector,careers_url=r.get("careers_url",website),ats=r.get("ats",""))
            n+=1
    return n

def seed_registry():
    # Primary universe: all configured global/country company watch targets.
    primary=ROOT/"config/company_universe.csv"
    n=_seed_file(primary) if primary.exists() else 0
    # Preserve the older Germany-specific registry as a supplemental source.
    legacy=ROOT/"config/remote_friendly_germany.csv"
    if legacy.exists(): n += _seed_file(legacy, default_country="Germany", default_regions="Europe")
    return n
