from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.db import conn
from app.services.apply import safe_profile
from app.services.exporter import export_tracker
conn().close(); safe_profile(); print('database: OK'); print('browser isolation: OK'); print('tracker export:', export_tracker())
