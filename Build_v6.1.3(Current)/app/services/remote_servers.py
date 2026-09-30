from __future__ import annotations
import aiohttp
from urllib.parse import urlparse
class RemoteServers:
 def __init__(self,db):self.db=db
 def list(self,gid):return self.db.all('SELECT * FROM remote_sources WHERE guild_id=? ORDER BY name',(gid,))
 async def manifest(self,row):
  headers={'Authorization':'Bearer '+row['auth_token']} if row['auth_token'] else {}
  async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30),headers=headers) as s:
   async with s.get(row['manifest_url']) as r:r.raise_for_status();data=await r.json(content_type=None)
  files=data.get('files',[]) if isinstance(data,dict) else data
  if not isinstance(files,list):raise ValueError('Manifest must be a JSON array or {"files": [...]}')
  return files
 async def test(self,gid,sid):
  row=self.db.one('SELECT * FROM remote_sources WHERE guild_id=? AND id=?',(gid,sid));return len(await self.manifest(row))
 async def sync(self,gid,sid):
  row=self.db.one('SELECT * FROM remote_sources WHERE guild_id=? AND id=?',(gid,sid));files=await self.manifest(row);seen=set()
  with self.db.connect() as c:
   for x in files:
    if not isinstance(x,dict):continue
    name=str(x.get('name') or '').strip();path=str(x.get('path') or name).strip();url=str(x.get('download_url') or '').strip();preview=str(x.get('preview_url') or '').strip()
    if not name or not url or urlparse(url).scheme not in ('http','https'):continue
    seen.add(path);c.execute('''INSERT INTO remote_items(source_id,guild_id,name,path,size,download_url,preview_url,available) VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(source_id,path) DO UPDATE SET name=excluded.name,size=excluded.size,download_url=excluded.download_url,preview_url=excluded.preview_url,available=1''',(sid,gid,name,path,int(x.get('size') or 0),url,preview or None))
   c.execute('UPDATE remote_items SET available=0 WHERE source_id=?',(sid,))
   for path in seen:c.execute('UPDATE remote_items SET available=1 WHERE source_id=? AND path=?',(sid,path))
   c.execute("UPDATE remote_sources SET last_sync=CURRENT_TIMESTAMP,last_status='online' WHERE id=?",(sid,))
  return len(seen)
