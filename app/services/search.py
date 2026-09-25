from __future__ import annotations
from dataclasses import dataclass
import math
from app.core.database import Database
@dataclass
class SearchPage:
 items:list[dict];page:int;page_size:int;total:int
 @property
 def pages(self):return max(1,math.ceil(self.total/self.page_size))
class SearchService:
 def __init__(self,db:Database):self.db=db
 def search(self,query,page=1,page_size=5,extension=None,max_results=250,guild_id=None):
  gid=0 if guild_id is None else int(guild_id);terms=[t.strip() for t in query.split() if t.strip()]
  items=[]
  if terms:
   match=' AND '.join('"'+t.replace('"','')+'"*' for t in terms)
   rows=self.db.all('SELECT kind,item_id FROM vault_fts WHERE guild_id=? AND vault_fts MATCH ? LIMIT ?',(gid,match,max_results))
   for x in rows:
    if x['kind']=='file':r=self.db.one("SELECT id,filename,folder,extension,category,file_size,full_path,'file' kind FROM vault_files WHERE guild_id=? AND id=?",(gid,x['item_id']))
    else:r=self.db.one("SELECT id,name filename,relative_path folder,'' extension,'folder' category,0 file_size,full_path,'folder' kind FROM vault_folders WHERE guild_id=? AND id=?",(gid,x['item_id']))
    if r and (not extension or (r['extension'] or '').casefold()==extension.lstrip('.').casefold()):items.append(dict(r))
  else:
   rows=self.db.all("SELECT id,filename,folder,extension,category,file_size,full_path,'file' kind FROM vault_files WHERE guild_id=? ORDER BY filename COLLATE NOCASE LIMIT ?",(gid,max_results));items=[dict(r) for r in rows if not extension or r['extension'].casefold()==extension.lstrip('.').casefold()]
  total=len(items);page=max(1,min(page,max(1,math.ceil(total/page_size))));start=(page-1)*page_size;return SearchPage(items[start:start+page_size],page,page_size,total)
 def random(self,guild_id=0):
  r=self.db.one('SELECT * FROM vault_files WHERE guild_id=? ORDER BY RANDOM() LIMIT 1',(guild_id,));return dict(r) if r else None
