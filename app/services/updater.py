from __future__ import annotations
import datetime as dt, json, os, shutil, sqlite3, tempfile, zipfile
from pathlib import Path

PROTECTED={'.env','data','config','linklists','credentials','google_drive','vault_index','backups','logs'}
SKIP={'.git','__pycache__','.venv','venv'}
class UpdateError(RuntimeError): pass

def _safe_extract(z,d):
 base=d.resolve()
 for i in z.infolist():
  q=(d/i.filename).resolve()
  if q!=base and base not in q.parents: raise UpdateError('Unsafe ZIP member: '+i.filename)
 z.extractall(d)

def _release_root(p,tmp):
 p=Path(p).expanduser().resolve()
 if p.is_dir(): root=p
 elif p.is_file() and zipfile.is_zipfile(p):
  root=tmp/'release';root.mkdir();
  with zipfile.ZipFile(p) as z:_safe_extract(z,root)
 else: raise UpdateError('Select a valid full build ZIP or extracted build folder.')
 # unwrap a single top-level directory (typical Build_vX.Y.Z.zip)
 kids=[x for x in root.iterdir() if x.name not in {'__MACOSX'}]
 if len(kids)==1 and kids[0].is_dir(): root=kids[0]
 # Special manifest packages remain supported, but are no longer required.
 if (root/'update_manifest.json').exists() and (root/'payload').is_dir(): root=root/'payload'
 return root

def create_backup(install):
 install=Path(install).resolve(); b=install/'backups'/('update_'+dt.datetime.now().strftime('%Y-%m-%d_%H%M%S'));b.mkdir(parents=True)
 copied=[]
 for name in PROTECTED:
  if name=='backups':continue
  s=install/name
  if not s.exists():continue
  d=b/name;d.parent.mkdir(parents=True,exist_ok=True)
  shutil.copytree(s,d,copy_function=shutil.copy2) if s.is_dir() else shutil.copy2(s,d);copied.append(name)
 (b/'backup_manifest.json').write_text(json.dumps({'protected':copied},indent=2),encoding='utf-8');return b

def restore_backup(install,b):
 install=Path(install).resolve();b=Path(b).resolve();m=json.loads((b/'backup_manifest.json').read_text(encoding='utf-8'))
 for name in m.get('protected',[]):
  s=b/name;d=install/name
  if d.exists(): shutil.rmtree(d) if d.is_dir() else d.unlink()
  d.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(s,d,copy_function=shutil.copy2) if s.is_dir() else shutil.copy2(s,d)

def _blocked(rel):
 parts=rel.parts
 return bool(parts and (parts[0] in PROTECTED or parts[0] in SKIP)) or '__pycache__' in parts or rel.suffix=='.pyc'

def install_update(install,source):
 install=Path(install).resolve(); backup=create_backup(install)
 with tempfile.TemporaryDirectory(prefix='420vault_update_') as td:
  src=_release_root(source,Path(td));count=0
  try:
   for f in src.rglob('*'):
    if not f.is_file():continue
    rel=f.relative_to(src)
    if _blocked(rel):continue
    d=install/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,d);count+=1
   # Existing databases are opened by the new build on restart, where normal schema migrations run.
   return {'files':count,'backup':str(backup),'source':str(src)}
  except Exception:
   restore_backup(install,backup);raise
