from __future__ import annotations
import os
from pathlib import Path
from app.core.database import Database
AUDIO={'wav','wave','aif','aiff','flac','mp3','ogg','m4a','aac','wma'}
MIDI={'mid','midi'}
PROJECT={'flp','als','logicx','rpp','ptx','band'}
ARCHIVE={'zip','rar','7z','tar','gz','bz2','xz'}
PRESET={'fst','fxp','fxb','vstpreset','aupreset','adg','adv','nmsv','ksd','h2p','spf','sbf','syx','bnk','bank','preset','patch','labx'}
SOUND={'sf2','sfz','nki','nkm','nkx','exs','rex','rx2','kit','drumkit'}
def category(ext):
 e=ext.lower().lstrip('.')
 if e in AUDIO:return 'audio'
 if e in MIDI:return 'midi'
 if e in PROJECT:return 'project'
 if e in ARCHIVE:return 'archive'
 if e in PRESET:return 'preset'
 if e in SOUND:return 'sound-library'
 return 'other'

class VaultIndexer:
 def __init__(self,db:Database):self.db=db
 def scan(self,guild_id:int,root:str,full=False,progress=None,batch_size=100):
  """Index a physical Vault without holding SQLite's writer lock for the whole scan.

  The old implementation wrapped os.walk + every INSERT in one transaction. On a
  large/removable Vault that could lock every Discord callback that touched the DB.
  This implementation commits small batches and updates FTS incrementally.
  """
  base=Path(root).expanduser().resolve()
  if not base.is_dir():raise ValueError(f'Vault path does not exist: {base}')
  seen_files=set();seen_dirs=set();added=updated=unchanged=folders=errors=processed=0
  batch_size=max(25,int(batch_size or 100))
  with self.db.connect() as c:
   # v5.5 full scans rebuild metadata in place; never erase a known-good index first.
   c.execute("INSERT INTO vault_scan_state(guild_id,last_status,last_error) VALUES(?,?,NULL) ON CONFLICT(guild_id) DO UPDATE SET last_status=excluded.last_status,last_error=NULL",(guild_id,'scanning'))
   c.commit()
   for current,dirnames,filenames in os.walk(base):
    cur=Path(current)
    dirnames[:]=[d for d in dirnames if not (cur/d).is_symlink()]
    rel='.' if cur==base else cur.relative_to(base).as_posix();seen_dirs.add(rel)
    try:
     st=cur.stat()
     c.execute('''INSERT INTO vault_folders(guild_id,name,relative_path,full_path,modified_at,child_count,available) VALUES(?,?,?,?,?,?,1) ON CONFLICT(guild_id,relative_path) DO UPDATE SET name=excluded.name,full_path=excluded.full_path,modified_at=excluded.modified_at,child_count=excluded.child_count,available=1''',(guild_id,base.name if cur==base else cur.name,rel,str(cur),st.st_mtime,len(dirnames)+len(filenames)))
     fid=c.execute('SELECT id FROM vault_folders WHERE guild_id=? AND relative_path=?',(guild_id,rel)).fetchone()['id']
     c.execute("DELETE FROM vault_fts WHERE guild_id=? AND kind='folder' AND item_id=?",(guild_id,fid))
     c.execute("INSERT INTO vault_fts(kind,item_id,guild_id,name,path,extension,category) VALUES('folder',?,?,?,?,'','folder')",(fid,guild_id,base.name if cur==base else cur.name,rel))
     folders+=1
    except OSError:errors+=1
    for name in filenames:
     fp=cur/name
     try:st=fp.stat()
     except OSError:errors+=1;continue
     processed+=1;fullp=str(fp);seen_files.add(fullp);ext=fp.suffix.lower().lstrip('.')
     old=c.execute('SELECT id,file_size,modified_at FROM vault_files WHERE guild_id=? AND full_path=?',(guild_id,fullp)).fetchone()
     if old and int(old['file_size'])==st.st_size and float(old['modified_at'])==st.st_mtime:
      unchanged+=1
     else:
      c.execute('''INSERT INTO vault_files(guild_id,filename,full_path,folder,extension,category,file_size,modified_at,available) VALUES(?,?,?,?,?,?,?,?,1) ON CONFLICT(guild_id,full_path) DO UPDATE SET filename=excluded.filename,folder=excluded.folder,extension=excluded.extension,category=excluded.category,file_size=excluded.file_size,modified_at=excluded.modified_at,available=1''',(guild_id,name,fullp,'' if cur==base else cur.relative_to(base).as_posix(),ext,category(ext),st.st_size,st.st_mtime))
      vid=c.execute('SELECT id FROM vault_files WHERE guild_id=? AND full_path=?',(guild_id,fullp)).fetchone()['id']
      c.execute("DELETE FROM vault_fts WHERE guild_id=? AND kind='file' AND item_id=?",(guild_id,vid))
      c.execute("INSERT INTO vault_fts(kind,item_id,guild_id,name,path,extension,category) VALUES('file',?,?,?,?,?,?)",(vid,guild_id,name,'' if cur==base else cur.relative_to(base).as_posix(),ext,category(ext)))
      updated+=bool(old);added+=not bool(old)
     if processed%batch_size==0:
      c.commit()
      if progress:progress({'status':'scanning','processed':processed,'folders':folders,'added':added,'updated':updated,'errors':errors,'current':str(cur)})
   c.commit()
   # v5.5: preserve metadata. A successful scan marks unseen rows offline instead of deleting them.
   stale_rows=[r for r in c.execute('SELECT id,full_path FROM vault_files WHERE guild_id=?',(guild_id,)).fetchall() if r['full_path'] not in seen_files]
   for n in range(0,len(stale_rows),batch_size):
    for r in stale_rows[n:n+batch_size]:c.execute('UPDATE vault_files SET available=0 WHERE guild_id=? AND id=?',(guild_id,r['id']))
    c.commit()
   dstale_rows=[r for r in c.execute('SELECT id,relative_path FROM vault_folders WHERE guild_id=?',(guild_id,)).fetchall() if r['relative_path'] not in seen_dirs]
   for n in range(0,len(dstale_rows),batch_size):
    for r in dstale_rows[n:n+batch_size]:c.execute('UPDATE vault_folders SET available=0 WHERE guild_id=? AND id=?',(guild_id,r['id']))
    c.commit()
   c.execute('INSERT INTO vault_scan_state(guild_id,last_scan,last_status,last_error) VALUES(?,CURRENT_TIMESTAMP,?,NULL) ON CONFLICT(guild_id) DO UPDATE SET last_scan=CURRENT_TIMESTAMP,last_status=excluded.last_status,last_error=NULL',(guild_id,'online'))
   c.commit()
  result={'added':added,'updated':updated,'unchanged':unchanged,'removed':0,'offline':len(stale_rows),'folders':folders,'folder_removed':0,'folder_offline':len(dstale_rows),'errors':errors,'processed':processed}
  if progress:progress(dict(result,status='complete',current='Complete'))
  return result
 def rebuild(self,root,guild_id=0):
  r=self.scan(guild_id,root,True);return r['added']+r['updated']+r['unchanged'],r['removed']
