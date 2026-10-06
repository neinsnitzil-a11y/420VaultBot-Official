from __future__ import annotations
import datetime as dt, hashlib, json, shutil, sqlite3, tempfile, zipfile, uuid
from pathlib import Path
PROTECTED={'.env','data','config','linklists','credentials','google_drive','vault_index','logs','tools','preview_cache','vault','downloads','exports'}
SKIP={'.git','__pycache__','.venv','venv','backups'}  # .venv/venv are preserved in place and never overwritten
class UpdateError(RuntimeError):pass

def _safe_extract(z,d):
 base=d.resolve()
 for i in z.infolist():
  q=(d/i.filename).resolve()
  if q!=base and base not in q.parents:raise UpdateError('Unsafe ZIP member: '+i.filename)
 z.extractall(d)
def _release_root(p,tmp):
 p=Path(p).expanduser().resolve()
 if p.is_dir():root=p
 elif p.is_file() and zipfile.is_zipfile(p):
  root=tmp/'release';root.mkdir();
  with zipfile.ZipFile(p) as z:_safe_extract(z,root)
 else:raise UpdateError('Select a valid full build ZIP or extracted build folder.')
 kids=[x for x in root.iterdir() if x.name!='__MACOSX']
 if len(kids)==1 and kids[0].is_dir():root=kids[0]
 if (root/'update_manifest.json').exists() and (root/'payload').is_dir():root=root/'payload'
 return root
def _hash_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def _sqlite_ok(p):
 try:
  with sqlite3.connect(p) as c:return c.execute('PRAGMA integrity_check').fetchone()[0].lower()=='ok'
 except Exception:return False
def _snapshot_db(src,dst):
 # SQLite's backup API takes a consistent snapshot from a live WAL database.
 dst.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(f'file:{src.as_posix()}?mode=ro',uri=True,timeout=30) as origin:
  with sqlite3.connect(dst,timeout=30) as target:
   origin.backup(target,pages=256,sleep=0.05)

def _copy_protected_tree(src,dst):
 # Do not replicate potentially inconsistent WAL/shm sidecars.
 dst.mkdir(parents=True,exist_ok=True)
 for file in src.rglob('*'):
  rel=file.relative_to(src);out=dst/rel
  if file.is_symlink():continue
  if file.is_dir():out.mkdir(parents=True,exist_ok=True);continue
  if file.suffix.lower() in ('.db-wal','.db-shm','.sqlite-wal','.sqlite-shm','.sqlite3-wal','.sqlite3-shm'):continue
  out.parent.mkdir(parents=True,exist_ok=True)
  if file.suffix.lower() in ('.db','.sqlite','.sqlite3'):_snapshot_db(file,out)
  else:shutil.copy2(file,out)

def create_backup(install,kind='manual',label=None):
 install=Path(install).resolve();stamp=dt.datetime.now().strftime('%Y-%m-%d_%H%M%S_%f')+'_'+uuid.uuid4().hex[:6];b=install/'backups'/f'{kind}_{stamp}';b.mkdir(parents=True,exist_ok=False);copied=[];files=[]
 for name in PROTECTED:
  s=install/name
  if not s.exists():continue
  d=b/name;d.parent.mkdir(parents=True,exist_ok=True)
  if s.is_dir():_copy_protected_tree(s,d)
  elif s.suffix.lower() in ('.db','.sqlite','.sqlite3'):_snapshot_db(s,d)
  else:shutil.copy2(s,d)
  copied.append(name)
 for f in b.rglob('*'):
  if f.is_file():files.append({'path':str(f.relative_to(b)),'sha256':_hash_file(f),'size':f.stat().st_size})
 dbchecks={}
 for f in b.rglob('*.db'):dbchecks[str(f.relative_to(b))]=_sqlite_ok(f)
 manifest={'kind':kind,'label':label,'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'protected':copied,'files':files,'sqlite_integrity':dbchecks}
 (b/'backup_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 if any(v is False for v in dbchecks.values()):raise UpdateError('Backup created but SQLite integrity verification failed.')
 ok,msg=verify_backup(b)
 if not ok:raise UpdateError('Backup verification failed: '+msg)
 return b
def verify_backup(b):
 b=Path(b).resolve();mp=b/'backup_manifest.json'
 if not mp.is_file():return False,'Missing backup_manifest.json'
 try:m=json.loads(mp.read_text(encoding='utf-8'))
 except Exception as e:return False,f'Invalid manifest: {e}'
 for row in m.get('files',[]):
  p=(b/row['path']).resolve()
  if b!=p and b not in p.parents:return False,'Unsafe backup manifest path'
  if not p.is_file() or _hash_file(p)!=row['sha256']:return False,'Checksum mismatch: '+row['path']
 for rel in m.get('sqlite_integrity',{}):
  dbpath=(b/rel).resolve()
  if b!=dbpath and b not in dbpath.parents:return False,'Unsafe backup SQLite path'
  if not _sqlite_ok(dbpath):return False,'SQLite integrity failed: '+rel
 return True,'Verified'
def restore_backup(install,b,make_safety=True):
 install=Path(install).resolve();b=Path(b).resolve();ok,msg=verify_backup(b)
 if not ok:raise UpdateError(msg)
 safety=create_backup(install,'pre_restore',b.name) if make_safety else None;m=json.loads((b/'backup_manifest.json').read_text(encoding='utf-8'))
 for name in m.get('protected',[]):
  if name not in PROTECTED:raise UpdateError('Unsafe restore target: '+str(name))
  s=b/name;d=install/name
  if d.exists():shutil.rmtree(d) if d.is_dir() else d.unlink()
  d.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(s,d,copy_function=shutil.copy2) if s.is_dir() else shutil.copy2(s,d)
 return safety
def list_backups(install,limit=50):
 p=Path(install)/'backups';return sorted([x for x in p.iterdir() if x.is_dir() and (x/'backup_manifest.json').is_file()],key=lambda x:x.stat().st_mtime,reverse=True)[:limit] if p.exists() else []
def prune_backups(install,daily=14,pre_update=10):
 rows=list_backups(install,500);groups={}
 for p in rows:groups.setdefault(p.name.split('_20',1)[0],[]).append(p)
 for kind,keep in [('daily',daily),('pre_update',pre_update)]:
  for p in groups.get(kind,[])[keep:]:shutil.rmtree(p,ignore_errors=True)
def daily_backup_if_due(install):
 rows=[p for p in list_backups(install,100) if p.name.startswith('daily_')]
 today=dt.datetime.now().date()
 if rows and dt.datetime.fromtimestamp(rows[0].stat().st_mtime).date()==today:return None
 b=create_backup(install,'daily');prune_backups(install);return b
def _blocked(rel):
 return bool(rel.parts and (rel.parts[0] in PROTECTED or rel.parts[0] in SKIP)) or '__pycache__' in rel.parts or rel.suffix=='.pyc'
def _auth_snapshot(install):
 # Updates must never invalidate existing accounts/sessions/profiles/licenses/2FA state.
 db=Path(install)/'data'/'420vault.db'
 if not db.is_file():return None
 try:
  with sqlite3.connect(db) as c:
   names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
   tracked=('auth_accounts','auth_sessions','user_profiles','licenses','subscriptions','guild_settings')
   return tuple((t,int(c.execute(f'SELECT COUNT(*) FROM \"{t}\"').fetchone()[0])) for t in tracked if t in names)
 except sqlite3.Error:return None
def install_update(install,source):
 install=Path(install).resolve();auth_before=_auth_snapshot(install);backup=create_backup(install,'pre_update',str(source));ok,msg=verify_backup(backup)
 if not ok:raise UpdateError('Pre-update backup verification failed: '+msg)
 with tempfile.TemporaryDirectory(prefix='420vault_update_') as td:
  src=_release_root(source,Path(td));count=0
  try:
   for f in src.rglob('*'):
    if not f.is_file():continue
    rel=f.relative_to(src)
    if _blocked(rel):continue
    d=install/rel;d.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,d);count+=1
   auth_after=_auth_snapshot(install)
   if auth_before is not None and auth_after!=auth_before:
    restore_backup(install,backup,False)
    raise UpdateError('Update preservation check failed: account/session/profile/license state changed during code installation.')
   prune_backups(install);return {'files':count,'backup':str(backup),'source':str(src),'persistent_state_preserved':auth_before is None or auth_after==auth_before,'virtualenv_preserved':True}
  except Exception:restore_backup(install,backup,False);raise
