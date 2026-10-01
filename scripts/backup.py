from pathlib import Path
import shutil, datetime
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'data'; out=ROOT/'data/backups'; out.mkdir(parents=True,exist_ok=True)
name=out/f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"; shutil.make_archive(str(name),'zip',src)
print(name.with_suffix('.zip'))
