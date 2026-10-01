import os,datetime
from ..db import conn

def daily_cap(): return max(0,int(os.getenv('RJP_MAX_DAILY_APPLICATIONS','30')))
def submitted_today():
    c=conn(); day=datetime.datetime.now(datetime.timezone.utc).date().isoformat(); n=c.execute("SELECT COUNT(*) FROM applications WHERE status='SUBMITTED_CONFIRMED' AND submitted_at LIKE ?",(day+'%',)).fetchone()[0]; c.close(); return n
def assert_can_submit():
    cap=daily_cap(); used=submitted_today()
    if cap and used>=cap: raise RuntimeError(f'APPLICATION_LIMIT_REACHED: {used}/{cap}')
    return {'cap':cap,'submitted':used,'remaining':max(0,cap-used) if cap else None}
