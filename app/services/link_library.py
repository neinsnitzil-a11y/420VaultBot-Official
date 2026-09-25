from __future__ import annotations
import asyncio, ipaddress, socket, re
from pathlib import Path
from urllib.parse import urljoin,urlparse,urlunparse,parse_qsl,urlencode
import aiohttp

TRACK={'utm_source','utm_medium','utm_campaign','utm_term','utm_content','fbclid','gclid'}
SKIP_EXT=('.jpg','.jpeg','.png','.gif','.webp','.svg','.css','.js','.ico','.woff','.woff2','.ttf')

def normalize_url(url:str)->str:
 p=urlparse(url.strip()); q=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if k.lower() not in TRACK]
 path=re.sub('/+','/',p.path or '/')
 return urlunparse((p.scheme.lower(),p.netloc.lower(),path.rstrip('/') or '/', '',urlencode(q),'')).strip()

def safe_public_host(host:str)->bool:
 try:
  infos=socket.getaddrinfo(host,None)
  for x in infos:
   ip=ipaddress.ip_address(x[4][0])
   if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:return False
  return True
 except Exception:return False

class LinkLibrary:
 def __init__(self,db):self.db=db
 @staticmethod
 def bundled_list_files():
  root=Path(__file__).resolve().parents[2]
  dirs=[root,root/'legacy',root/'data'/'link_lists']
  pats=('list.txt','lists.txt','links_part_*.txt','lists_part_*.txt')
  out=[];seen=set()
  for d in dirs:
   if not d.is_dir():continue
   for pat in pats:
    for f in d.glob(pat):
     try:key=str(f.resolve()).lower()
     except Exception:key=str(f).lower()
     if key not in seen and f.is_file():seen.add(key);out.append(f)
  def partno(f):
   m=re.search(r'(?:links|lists)_part_(\d+)\.txt$',f.name,re.I)
   if m:return int(m.group(1))
   return 1 if f.name.lower() in ('list.txt','lists.txt') else 999999
  return sorted(out,key=lambda f:(partno(f),f.name.lower()))
 def import_bundled_lists(self,gid):
  results=[]
  for f in self.bundled_list_files():
   m=re.search(r'(?:links|lists)_part_(\d+)\.txt$',f.name,re.I);n=int(m.group(1)) if m else 1
   name='Link Library' if n==1 else f'Link Library Part {n}'
   # Existing managed list means this shipped part was already indexed for this guild.
   if self.db.one('SELECT id FROM link_lists WHERE guild_id=? AND name=?',(gid,name)):continue
   try:
    urls=[x.strip() for x in f.read_text(encoding='utf-8',errors='ignore').splitlines() if x.strip().startswith(('http://','https://'))]
    r=self.ingest(gid,name,urls,'bundled_file',str(f),f'Auto-loaded from {f.name}');r['file']=str(f);results.append(r)
   except Exception:continue
  return results
 @staticmethod
 def next_part_path():
  root=Path(__file__).resolve().parents[2];d=root/'data'/'link_lists';d.mkdir(parents=True,exist_ok=True)
  nums=[]
  for f in LinkLibrary.bundled_list_files():
   m=re.search(r'(?:links|lists)_part_(\d+)\.txt$',f.name,re.I)
   if m:nums.append(int(m.group(1)))
   elif f.name.lower() in ('list.txt','lists.txt'):nums.append(1)
  n=max(nums or [1])+1
  while (d/f'links_part_{n}.txt').exists():n+=1
  return d/f'links_part_{n}.txt',n
 def save_scrape_part(self,gid,urls,target=None):
  path,n=self.next_part_path();path.write_text('\n'.join(urls)+'\n',encoding='utf-8')
  r=self.ingest(gid,f'Link Library Part {n}',urls,'scrape_file',target,f'Auto-created by web scraper as {path.name}')
  r.update({'path':str(path),'part':n});return r
 def lists(self,gid):return self.db.all('SELECT l.*,COUNT(m.link_id) link_count FROM link_lists l LEFT JOIN link_list_members m ON m.list_id=l.id WHERE l.guild_id=? GROUP BY l.id ORDER BY l.name',(gid,))
 def ingest(self,gid,name,urls,source_type='import',source_url=None,description=''):
  lid=self.db.execute('INSERT OR IGNORE INTO link_lists(guild_id,name,description,source_type,source_url) VALUES(?,?,?,?,?)',(gid,name,description,source_type,source_url))
  if not lid:lid=self.db.one('SELECT id FROM link_lists WHERE guild_id=? AND name=?',(gid,name))['id']
  added=existing=invalid=0
  with self.db.connect() as c:
   for raw in urls:
    try:
     u=normalize_url(raw); p=urlparse(u)
     if p.scheme not in ('http','https') or not p.hostname:invalid+=1;continue
     row=c.execute('SELECT id FROM links WHERE guild_id=? AND normalized_url=?',(gid,u)).fetchone()
     if row:linkid=row['id'];existing+=1
     else:
      cur=c.execute('INSERT INTO links(guild_id,url,normalized_url,domain) VALUES(?,?,?,?)',(gid,raw.strip(),u,p.hostname.lower()));linkid=cur.lastrowid
      c.execute('INSERT INTO link_fts(link_id,guild_id,url,domain,title) VALUES(?,?,?,?,?)',(linkid,gid,u,p.hostname.lower(),''));added+=1
     c.execute('INSERT OR IGNORE INTO link_list_members(list_id,link_id) VALUES(?,?)',(lid,linkid))
    except Exception:
     invalid+=1
   c.execute('UPDATE link_lists SET updated_at=CURRENT_TIMESTAMP WHERE id=?',(lid,))
  return {'list_id':lid,'added':added,'existing':existing,'invalid':invalid}

class UniversalScraper:
 def __init__(self,max_pages=2000,concurrency=6,include_subdomains=False):self.max_pages=max(1,min(max_pages,20000));self.concurrency=max(1,min(concurrency,12));self.include_subdomains=include_subdomains
 async def scrape(self,target,progress=None):
  start=normalize_url(target); root=urlparse(start)
  if root.scheme not in ('http','https') or not root.hostname or not safe_public_host(root.hostname):raise ValueError('Target must be a public HTTP/HTTPS website.')
  q=asyncio.Queue();await q.put(start);seen=set();found=set();errors=0;lock=asyncio.Lock();recent=[]
  timeout=aiohttp.ClientTimeout(total=25)
  headers={'User-Agent':'Mozilla/5.0 (compatible; 420VaultBot/3.7 LinkIndexer)'}
  async with aiohttp.ClientSession(timeout=timeout,headers=headers) as sess:
   async def worker():
    nonlocal errors
    while len(seen)<self.max_pages:
     try:u=await asyncio.wait_for(q.get(),.5)
     except asyncio.TimeoutError:
      if q.empty():return
      continue
     if u in seen:q.task_done();continue
     seen.add(u)
     try:
      host=urlparse(u).hostname
      if not host or not safe_public_host(host):raise ValueError('unsafe host')
      async with sess.get(u,allow_redirects=True,max_redirects=5) as r:
       final=r.url;fh=final.host
       if not fh or not safe_public_host(fh):raise ValueError('unsafe redirect')
       if r.status>=400:raise ValueError(f'HTTP {r.status}')
       ct=r.headers.get('content-type','')
       if 'text/html' not in ct:continue
       text=await r.text(errors='ignore')
       for href in re.findall(r'''(?:href|src)=["']([^"'#]+)''',text,re.I):
        v=normalize_url(urljoin(str(final),href));p=urlparse(v)
        if p.scheme not in ('http','https') or not p.hostname:continue
        
        if v not in found:
         found.add(v);recent.append(v);del recent[:-12]
        same=p.hostname==root.hostname or (self.include_subdomains and p.hostname.endswith('.'+root.hostname))
        if same and not p.path.lower().endswith(SKIP_EXT) and v not in seen and q.qsize()<self.max_pages:await q.put(v)
     except Exception:errors+=1
     finally:
      q.task_done()
      if progress:await progress(len(seen),len(found),errors,q.qsize(),u,list(recent))
   tasks=[asyncio.create_task(worker()) for _ in range(self.concurrency)]
   await q.join()
   for t in tasks:t.cancel()
   await asyncio.gather(*tasks,return_exceptions=True)
  return sorted(found),{'pages':len(seen),'links':len(found),'errors':errors}
