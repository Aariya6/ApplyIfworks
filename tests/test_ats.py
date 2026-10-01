from app.services.ats import audit_pdf
from pathlib import Path

def test_module_imports():
    from app.adapters.feeds import RemoteOK,ArbeitNow,Remotive
    from app.adapters.ats import Greenhouse,Lever,SmartRecruiters
    assert RemoteOK.name=='remoteok'
    assert Greenhouse.name=='greenhouse'
