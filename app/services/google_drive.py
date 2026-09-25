from __future__ import annotations
import asyncio, json, os, re, time, tempfile, shutil, zipfile
from collections import deque
from pathlib import Path
from urllib.parse import quote
import aiohttp

FOLDER='application/vnd.google-apps.folder'
EXPORTS={
 'application/vnd.google-apps.document':('application/pdf','.pdf'),
 'application/vnd.google-apps.spreadsheet':('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.xlsx'),
 'application/vnd.google-apps.presentation':('application/pdf','.pdf'),
}

def folder_id(value:str)->str:
 value=(value or '').strip()
 m=re.search(r'/folders/([A-Za-z0-9_-]+)',value)
 return m.group(1) if m else value.split('?')[0].strip()

class GoogleDriveService:
 def __init__(self,db):
  self.db=db;self._token=None;self._token_exp=0
  self.secret_path=Path(os.getenv('GOOGLE_DRIVE_SECRET_FILE','data/google_drive_secrets.json'))
  self._sync_tasks={}
  self._progress={}
  self._sync_locks={}
  self._token_lock=asyncio.Lock()
  self._archive_tasks={}
  self._archive_progress={}
 def credentials(self):
  data={}
  try:
   if self.secret_path.is_file(): data=json.loads(self.secret_path.read_text(encoding='utf-8'))
  except Exception: data={}
  return {
   'client_id':str(data.get('client_id') or os.getenv('GOOGLE_DRIVE_CLIENT_ID','')).strip(),
   'client_secret':str(data.get('client_secret') or os.getenv('GOOGLE_DRIVE_CLIENT_SECRET','')).strip(),
   'refresh_token':str(data.get('refresh_token') or os.getenv('GOOGLE_DRIVE_REFRESH_TOKEN','')).strip(),
  }
 def credentials_status(self):
  c=self.credentials();return {k:bool(v) for k,v in c.items()}
 def save_credentials(self,client_id,client_secret,refresh_token):
  self.secret_path.parent.mkdir(parents=True,exist_ok=True)
  self.secret_path.write_text(json.dumps({'client_id':client_id.strip(),'client_secret':client_secret.strip(),'refresh_token':refresh_token.strip()},indent=2),encoding='utf-8')
  try: os.chmod(self.secret_path,0o600)
  except OSError: pass
  self._token=None;self._token_exp=0
 def clear_credentials(self):
  if self.secret_path.exists(): self.secret_path.unlink()
  self._token=None;self._token_exp=0
 async def token(self):
  # Prevent simultaneous refreshes from stalling multiple Discord tasks.
  async with self._token_lock:
   if self._token and time.time()<self._token_exp-60:return self._token
   c=await asyncio.to_thread(self.credentials);refresh=c['refresh_token'];cid=c['client_id'];secret=c['client_secret']
   if not (refresh and cid and secret):raise RuntimeError('Google Drive OAuth is not configured. Set GOOGLE_DRIVE_CLIENT_ID, GOOGLE_DRIVE_CLIENT_SECRET, and GOOGLE_DRIVE_REFRESH_TOKEN.')
   timeout=aiohttp.ClientTimeout(total=35,connect=10,sock_read=30)
   async with aiohttp.ClientSession(timeout=timeout) as sess:
    async with sess.post('https://oauth2.googleapis.com/token',data={'client_id':cid,'client_secret':secret,'refresh_token':refresh,'grant_type':'refresh_token'}) as r:
     data=await r.json()
     if r.status>=300:raise RuntimeError('Google OAuth refresh failed: '+str(data.get('error_description') or data.get('error') or r.status))
   self._token=data['access_token'];self._token_exp=time.time()+int(data.get('expires_in',3600));return self._token
 async def api(self,path,params=None):
  tok=await self.token();url='https://www.googleapis.com/drive/v3/'+path
  async with aiohttp.ClientSession(headers={'Authorization':'Bearer '+tok}) as s:
   async with s.get(url,params=params,timeout=60) as r:
    data=await r.json()
    if r.status>=300:raise RuntimeError(str(data.get('error',{}).get('message') or r.status))
    return data
 async def get_meta(self,file_id):
  return await self.api('files/'+quote(file_id,safe=''),{'fields':'id,name,mimeType,size,modifiedTime,webViewLink,parents,trashed','supportsAllDrives':'true'})
 async def list_children(self,parent,page_token=None):
  q=f"'{parent}' in parents and trashed=false"
  return await self.api('files',{'q':q,'fields':'nextPageToken,files(id,name,mimeType,size,modifiedTime,webViewLink,parents)','pageSize':'1000','pageToken':page_token or '','supportsAllDrives':'true','includeItemsFromAllDrives':'true','corpora':'allDrives'})
 def save_root(self,gid,root):
  rid=folder_id(root)
  if not rid: raise RuntimeError('Enter a Google Drive folder URL or folder ID.')
  self.db.execute('INSERT INTO drive_sources(guild_id,root_file_id,root_name,enabled,last_status) VALUES(?,?,?,?,?) ON CONFLICT(guild_id) DO UPDATE SET root_file_id=excluded.root_file_id,enabled=1,last_status=excluded.last_status',(gid,rid,'Saved Drive Folder',1,'saved - connection not tested'))
  return rid
 async def configure(self,gid,root):
  rid=self.save_root(gid,root)
  m=await self.get_meta(rid)
  if m.get('mimeType')!=FOLDER:raise RuntimeError('Configured Google Drive root must be a folder.')
  self.db.execute('UPDATE drive_sources SET root_name=?,enabled=1,last_status=? WHERE guild_id=?',(m['name'],'connected',gid))
  return m
 async def test_connection(self,gid):
  src=self.db.one('SELECT * FROM drive_sources WHERE guild_id=?',(gid,))
  if not src: raise RuntimeError('Save a Google Drive root folder first.')
  m=await self.get_meta(src['root_file_id'])
  if m.get('mimeType')!=FOLDER: raise RuntimeError('The saved Google Drive ID is not a folder.')
  self.db.execute('UPDATE drive_sources SET root_name=?,enabled=1,last_status=? WHERE guild_id=?',(m['name'],'connected',gid))
  return m
 async def start_sync(self,gid):
  task=self._sync_tasks.get(gid)
  if task and not task.done():return False
  task=asyncio.create_task(self._sync_runner(gid),name=f'drive-sync-{gid}')
  self._sync_tasks[gid]=task
  return True
 async def _sync_runner(self,gid):
  try:
   await self.sync(gid)
  except Exception as e:
   self._progress[gid]={'status':'failed','indexed':self._progress.get(gid,{}).get('indexed',0),'error':f'{type(e).__name__}: {e}','started':self._progress.get(gid,{}).get('started',time.time())}
   await asyncio.to_thread(self.db.execute,'UPDATE drive_sources SET last_status=? WHERE guild_id=?',(f'failed: {str(e)[:180]}',gid))
  finally:
   self._sync_tasks.pop(gid,None)
 def sync_progress(self,gid):
  p=dict(self._progress.get(gid,{}) or {})
  t=self._sync_tasks.get(gid);p['running']=bool(t and not t.done())
  if p.get('started'):p['elapsed']=max(0,int(time.time()-p['started']))
  return p
 def _write_drive_page(self,gid,parent,parent_path,files):
  # Keep each SQLite writer transaction intentionally small. Large Drive pages can
  # contain 1,000 items; one giant transaction starves Discord callbacks.
  rows=[];folders=[]
  for off in range(0,len(files),100):
   batch=files[off:off+100]
   with self.db.connect() as c:
    for f in batch:
     fid=f['id'];isfolder=f['mimeType']==FOLDER;path=(parent_path+'/'+f['name']).strip('/')
     c.execute("""INSERT INTO drive_items(guild_id,file_id,parent_id,name,mime_type,size,modified_time,web_view_link,relative_path,is_folder,available)
      VALUES(?,?,?,?,?,?,?,?,?,?,1) ON CONFLICT(guild_id,file_id) DO UPDATE SET parent_id=excluded.parent_id,name=excluded.name,mime_type=excluded.mime_type,size=excluded.size,modified_time=excluded.modified_time,web_view_link=excluded.web_view_link,relative_path=excluded.relative_path,is_folder=excluded.is_folder,available=1""",(gid,fid,parent,f['name'],f['mimeType'],int(f.get('size') or 0),f.get('modifiedTime'),f.get('webViewLink'),path,1 if isfolder else 0))
     rows.append(fid)
     if isfolder:folders.append((fid,path))
  return rows,folders
 def _mark_stale(self,gid,seen):
  # Never run one full-table UPDATE while Discord is live. Walk SQLite rowids in
  # bounded batches so other readers/writers get frequent scheduling windows.
  last=0
  while True:
   with self.db.connect() as c:rows=c.execute('SELECT rowid FROM drive_items WHERE guild_id=? AND rowid>? ORDER BY rowid LIMIT 500',(gid,last)).fetchall()
   if not rows:break
   ids=[r['rowid'] for r in rows];last=ids[-1]
   with self.db.connect() as c:c.execute('UPDATE drive_items SET available=0 WHERE rowid IN ('+','.join('?'*len(ids))+')',ids)
  ids=list(seen)
  for off in range(0,len(ids),250):
   chunk=ids[off:off+250]
   with self.db.connect() as c:c.execute('UPDATE drive_items SET available=1 WHERE guild_id=? AND file_id IN ('+','.join('?'*len(chunk))+')',(gid,*chunk))
 def _rebuild_drive_fts(self,gid,progress=None):
  # Rebuild in bounded transactions. This is the most important responsiveness
  # change for very large Drives because FTS insertion can otherwise monopolize SQLite.
  with self.db.connect() as c:c.execute('DELETE FROM drive_fts WHERE guild_id=?',(gid,))
  last='';done=0
  while True:
   with self.db.connect() as c:
    rows=c.execute('SELECT file_id,name,relative_path,mime_type FROM drive_items WHERE guild_id=? AND available=1 AND file_id>? ORDER BY file_id LIMIT 500',(gid,last)).fetchall()
   if not rows:break
   with self.db.connect() as c:
    c.executemany('INSERT INTO drive_fts(file_id,guild_id,name,path,mime_type) VALUES(?,?,?,?,?)',[(r['file_id'],gid,r['name'],r['relative_path'],r['mime_type']) for r in rows])
   last=rows[-1]['file_id'];done+=len(rows)
   if progress:progress(done)
  return done
 async def sync(self,gid):
  # One sync per guild. Network I/O stays async; every SQLite-heavy section runs
  # in a worker thread and uses bounded transactions.
  lock=self._sync_locks.setdefault(gid,asyncio.Lock())
  if lock.locked():raise RuntimeError('A Google Drive sync is already running for this server.')
  async with lock:
   src=await asyncio.to_thread(self.db.one,'SELECT * FROM drive_sources WHERE guild_id=? AND enabled=1',(gid,))
   if not src:raise RuntimeError('Google Drive is not configured for this server.')
   root=src['root_file_id'];queue=deque([(root,'')]);seen=set();started=time.time();pages=0
   self._progress[gid]={'status':'syncing','indexed':0,'folders_queued':1,'pages':0,'started':started,'error':None,'current':'/'}
   await asyncio.to_thread(self.db.execute,'UPDATE drive_sources SET last_status=?,item_count=? WHERE guild_id=?',('syncing',0,gid))
   while queue:
    parent,parent_path=queue.popleft();page=None
    while True:
     data=await self.list_children(parent,page);files=data.get('files',[])
     ids,folders=await asyncio.to_thread(self._write_drive_page,gid,parent,parent_path,files)
     seen.update(ids);queue.extend(folders);pages+=1
     self._progress[gid].update(indexed=len(seen),folders_queued=len(queue),pages=pages,current=parent_path or '/')
     # Persist status less aggressively; progress is served from memory while running.
     if pages==1 or pages%10==0:
      await asyncio.to_thread(self.db.execute,'UPDATE drive_sources SET item_count=?,last_status=? WHERE guild_id=?',(len(seen),'syncing',gid))
     await asyncio.sleep(0)
     page=data.get('nextPageToken')
     if not page:break
   self._progress[gid].update(status='finalizing',indexed=len(seen),current='Marking stale Drive entries')
   await asyncio.to_thread(self._mark_stale,gid,seen)
   self._progress[gid].update(current='Building search index',fts_indexed=0)
   def fts_progress(n):self._progress[gid]['fts_indexed']=n
   await asyncio.to_thread(self._rebuild_drive_fts,gid,fts_progress)
   await asyncio.to_thread(self.db.execute,"UPDATE drive_sources SET last_sync=CURRENT_TIMESTAMP,last_status='ready',item_count=? WHERE guild_id=?",(len(seen),gid))
   self._progress[gid].update(status='ready',indexed=len(seen),current='Complete')
   return len(seen)
 def archive_progress(self,gid):
  p=dict(self._archive_progress.get(gid,{}) or {});t=self._archive_tasks.get(gid);p['running']=bool(t and not t.done());return p
 async def start_archive_parse(self,gid):
  t=self._archive_tasks.get(gid)
  if t and not t.done():return False
  self._archive_tasks[gid]=asyncio.create_task(self._archive_parse_runner(gid),name=f'drive-archive-parse-{gid}');return True
 async def _archive_parse_runner(self,gid):
  try:await self.parse_archives(gid)
  except Exception as e:
   self._archive_progress[gid]={'status':'failed','error':f'{type(e).__name__}: {e}'}
   await asyncio.to_thread(self.db.execute,'DELETE FROM drive_archive_entries WHERE guild_id=? AND archive_file_id NOT IN (SELECT file_id FROM drive_items WHERE guild_id=? AND available=1)',(gid,gid))
   await asyncio.to_thread(self._rebuild_archive_fts,gid)
   await asyncio.to_thread(self.db.execute,"INSERT INTO drive_archive_state(guild_id,last_run,last_status,last_error) VALUES(?,CURRENT_TIMESTAMP,'failed',?) ON CONFLICT(guild_id) DO UPDATE SET last_run=CURRENT_TIMESTAMP,last_status='failed',last_error=excluded.last_error",(gid,str(e)[:500]))
  finally:self._archive_tasks.pop(gid,None)
 def _read_archive_members(self,path:Path):
  out=[];low=path.name.lower()
  if low.endswith('.zip'):
   with zipfile.ZipFile(path) as z:
    for x in z.infolist():
     if not x.is_dir():out.append((x.filename,int(x.file_size or 0)))
  elif low.endswith('.rar'):
   try:import rarfile
   except ImportError:raise RuntimeError('RAR parsing requires the rarfile Python package. Run pip install -r requirements.txt.')
   with rarfile.RarFile(path) as r:
    for x in r.infolist():
     if not x.isdir():out.append((x.filename,int(x.file_size or 0)))
  return out
 def _save_archive_members(self,gid,item,members):
  with self.db.connect() as c:
   c.execute('DELETE FROM drive_archive_entries WHERE guild_id=? AND archive_file_id=?',(gid,item['file_id']))
   for member,size in members:
    c.execute('INSERT OR REPLACE INTO drive_archive_entries(guild_id,archive_file_id,archive_name,member_name,member_path,member_size,archive_modified_time) VALUES(?,?,?,?,?,?,?)',(gid,item['file_id'],item['name'],Path(member).name,member,size,item.get('modified_time')))
  self._rebuild_archive_fts(gid)
 def _rebuild_archive_fts(self,gid):
  with self.db.connect() as c:
   c.execute('DELETE FROM drive_archive_fts WHERE guild_id=?',(gid,))
   c.execute('INSERT INTO drive_archive_fts(entry_id,guild_id,archive_name,member_name,member_path) SELECT id,guild_id,archive_name,member_name,member_path FROM drive_archive_entries WHERE guild_id=?',(gid,))
 async def parse_archives(self,gid):
  rows=[dict(r) for r in await asyncio.to_thread(self.db.all,"SELECT * FROM drive_items WHERE guild_id=? AND available=1 AND is_folder=0 AND (lower(name) LIKE '%.zip' OR lower(name) LIKE '%.rar') ORDER BY name",(gid,))]
  max_bytes=int(os.getenv('GOOGLE_DRIVE_ARCHIVE_PARSE_MAX_BYTES',str(2*1024*1024*1024)));parsed=0;entries=0;skipped=0
  self._archive_progress[gid]={'status':'parsing','total':len(rows),'parsed':0,'entries':0,'skipped':0,'current':''}
  tmp=Path(tempfile.mkdtemp(prefix='420drive_archives_'))
  try:
   for idx,item in enumerate(rows,1):
    self._archive_progress[gid].update(current=item['name'],current_number=idx)
    size=int(item.get('size') or 0)
    if size and size>max_bytes:skipped+=1;self._archive_progress[gid]['skipped']=skipped;continue
    target=tmp/(item['file_id']+Path(item['name']).suffix.lower())
    try:
     downloaded=await self.download(item['file_id'],tmp,item.get('mime_type') or '',target.name)
     members=await asyncio.to_thread(self._read_archive_members,downloaded)
     await asyncio.to_thread(self._save_archive_members,gid,item,members);parsed+=1;entries+=len(members)
    except Exception as e:
     skipped+=1;self._archive_progress[gid]['last_error']=f'{item["name"]}: {e}'[:300]
    finally:
     try:
      if target.exists():target.unlink()
     except OSError:pass
    self._archive_progress[gid].update(parsed=parsed,entries=entries,skipped=skipped)
    await asyncio.sleep(0)
   await asyncio.to_thread(self.db.execute,'DELETE FROM drive_archive_entries WHERE guild_id=? AND archive_file_id NOT IN (SELECT file_id FROM drive_items WHERE guild_id=? AND available=1)',(gid,gid))
   await asyncio.to_thread(self._rebuild_archive_fts,gid)
   await asyncio.to_thread(self.db.execute,"INSERT INTO drive_archive_state(guild_id,last_run,last_status,archives_parsed,entries_indexed,last_error) VALUES(?,CURRENT_TIMESTAMP,'ready',?,?,NULL) ON CONFLICT(guild_id) DO UPDATE SET last_run=CURRENT_TIMESTAMP,last_status='ready',archives_parsed=excluded.archives_parsed,entries_indexed=excluded.entries_indexed,last_error=NULL",(gid,parsed,entries))
   self._archive_progress[gid].update(status='ready',current='Complete')
  finally:await asyncio.to_thread(shutil.rmtree,tmp,True)
  return {'parsed':parsed,'entries':entries,'skipped':skipped}
 def search(self,gid,query,page=1,page_size=10,max_results=500):
  query=(query or '').strip();off=max(0,(page-1)*page_size)
  if not query:
   rows=self.db.all('SELECT * FROM drive_items WHERE guild_id=? AND available=1 ORDER BY is_folder DESC,name COLLATE NOCASE LIMIT ? OFFSET ?',(gid,page_size,off));total=self.db.one('SELECT COUNT(*) n FROM drive_items WHERE guild_id=? AND available=1',(gid,))['n'];return [dict(r) for r in rows],min(total,max_results)
  terms=re.findall(r'[\w.-]+',query)[:10];match=' AND '.join('"'+t.replace('"','')+'"*' for t in terms)
  direct=[dict(r) for r in self.db.all('SELECT d.* FROM drive_fts f JOIN drive_items d ON d.guild_id=f.guild_id AND d.file_id=f.file_id WHERE drive_fts MATCH ? AND d.guild_id=? AND d.available=1 LIMIT ?',(match,gid,max_results))]
  archive=[]
  for r in self.db.all('SELECT a.*,d.size archive_size,d.mime_type,d.web_view_link,d.relative_path FROM drive_archive_fts f JOIN drive_archive_entries a ON a.guild_id=f.guild_id AND a.id=f.entry_id JOIN drive_items d ON d.guild_id=a.guild_id AND d.file_id=a.archive_file_id WHERE drive_archive_fts MATCH ? AND a.guild_id=? AND d.available=1 LIMIT ?',(match,gid,max_results)):
   x=dict(r);archive.append({'file_id':'archive:'+str(x['id']),'archive_entry_id':x['id'],'archive_file_id':x['archive_file_id'],'name':x['member_name'],'mime_type':'application/x-420vault-archive-entry','size':x['member_size'],'modified_time':x.get('archive_modified_time'),'web_view_link':x.get('web_view_link'),'relative_path':f'{x["archive_name"]} :: {x["member_path"]}','is_folder':0,'available':1,'archive_name':x['archive_name'],'archive_size':x['archive_size']})
  combined=(direct+archive)[:max_results];total=len(combined);return combined[off:off+page_size],total

 async def download_folder_zip(self,gid,folder_id,folder_name,dest:Path,max_files=10000):
  """Recursively download a Drive folder and return a ZIP preserving its tree."""
  import shutil as _shutil
  work=dest/(folder_name.replace('/','_')+'_folder');work.mkdir(parents=True,exist_ok=True);queue=[(folder_id,work)];count=0
  while queue:
   parent,local=queue.pop(0);page=None
   while True:
    data=await self.list_children(parent,page)
    for item in data.get('files',[]):
     count+=1
     if count>max_files:raise RuntimeError(f'Folder contains more than {max_files:,} items; ZIP creation stopped for safety.')
     safe=Path(item['name']).name or 'item'
     if item.get('mimeType')==FOLDER:
      child=local/safe;child.mkdir(parents=True,exist_ok=True);queue.append((item['id'],child))
     else:await self.download(item['id'],local,item.get('mimeType') or '',safe)
    page=data.get('nextPageToken')
    if not page:break
  archive=await asyncio.to_thread(_shutil.make_archive,str(dest/(folder_name.replace('/','_') or 'drive_folder')),'zip',work.parent,work.name)
  return Path(archive),count
 def children(self,gid,parent,page=1,page_size=10):
  off=(page-1)*page_size;rows=self.db.all('SELECT * FROM drive_items WHERE guild_id=? AND parent_id=? AND available=1 ORDER BY is_folder DESC,name COLLATE NOCASE LIMIT ? OFFSET ?',(gid,parent,page_size,off));total=self.db.one('SELECT COUNT(*) n FROM drive_items WHERE guild_id=? AND parent_id=? AND available=1',(gid,parent))['n'];return [dict(r) for r in rows],total
 async def download(self,file_id,dest:Path,mime_type:str,name:str):
  tok=await self.token();export=EXPORTS.get(mime_type)
  if export:url='https://www.googleapis.com/drive/v3/files/'+quote(file_id,safe='')+'/export?mimeType='+quote(export[0],safe='');dest=dest/(name+export[1] if not name.lower().endswith(export[1]) else name)
  else:url='https://www.googleapis.com/drive/v3/files/'+quote(file_id,safe='')+'?alt=media&supportsAllDrives=true';dest=dest/name
  async with aiohttp.ClientSession(headers={'Authorization':'Bearer '+tok}) as s:
   async with s.get(url,timeout=aiohttp.ClientTimeout(total=None,sock_connect=30,sock_read=300)) as r:
    if r.status>=300:raise RuntimeError('Google Drive download failed: '+str(r.status))
    with open(dest,'wb') as f:
     async for chunk in r.content.iter_chunked(1024*1024):f.write(chunk)
  return dest
