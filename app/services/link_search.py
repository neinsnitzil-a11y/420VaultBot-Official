from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import math,re,threading

@dataclass
class LinkPage:
    items:list[str]; page:int; page_size:int; total:int
    @property
    def pages(self): return max(1,math.ceil(self.total/self.page_size))

class LinkSearchService:
    """Loads the large legacy link lists once, pre-normalizes them, and caches queries.

    Page changes never rescan the 200k+ source list: the first query creates a capped
    result set and Previous/Next only slice that cached set.
    """
    def __init__(self, root:Path, db=None):
        self.root=Path(root); self.db=db; self.links:list[str]=[]; self._records:list[tuple[str,str,str]]=[]
        self.sources:list[Path]=[]; self._cache=OrderedDict(); self._cache_lock=threading.Lock(); self.reload()
    def discover(self):
        candidates=[self.root/f'lists{suffix}.txt' for suffix in ['', '_part_2','_part_3','_part_4']]
        legacy=self.root/'legacy'; candidates += [legacy/f'lists{suffix}.txt' for suffix in ['', '_part_2','_part_3','_part_4']]
        return [p for p in candidates if p.is_file()]
    @staticmethod
    def clean_path(url:str):
        path=urlparse(url).path.strip('/').replace('-',' ').replace('_',' ')
        path=re.sub(r'\.(html|php|asp|aspx|jsp|htm|exe|zip|rar|mp3|wav|midi|dmg|pkg)$','',path,flags=re.I)
        path=re.sub(r'\b(free|download|effect|effects|collection|collections|preset|presets|kit|kits|pack|packs|bank|banks|vst|midi|loops|one\s*shots|drum\s*kits|sound|sounds|windows|mac|macos|installer|win|setup)\b','',path,flags=re.I)
        return re.sub(r'\s+',' ',path).strip().lower()
    def reload(self):
        self.sources=self.discover(); seen=set(); out=[]; records=[]
        for p in self.sources:
            with p.open('r',encoding='utf-8',errors='ignore') as f:
                for line in f:
                    s=line.strip()
                    if not s or s.startswith(('#','---')) or s in seen: continue
                    seen.add(s); out.append(s)
                    raw=urlparse(s).path.strip('/').lower(); records.append((s,raw,self.clean_path(s)))
        self.links=out; self._records=records
        with self._cache_lock:self._cache.clear()
        return len(out)
    @staticmethod
    def _record_matches(raw:str,clean:str,terms:tuple[str,...]):
        for t in terms:
            if t=='win': ok=('windows' in raw or '.exe' in raw or 'installer-win' in raw or 'win-installer' in raw or 'for-windows' in raw)
            elif t=='mac': ok=('mac' in raw or 'macos' in raw or '.dmg' in raw or '.pkg' in raw or 'installer-mac' in raw or 'for-mac' in raw)
            elif t=='installer': ok=('installer' in raw or '.exe' in raw or '.dmg' in raw or '.pkg' in raw or 'setup' in raw)
            else: ok=(t in clean or t in raw)
            if not ok:return False
        return True
    def _results(self,query:str,max_results:int):
        terms=tuple(t for t in query.lower().split() if t); key=(terms,max_results)
        with self._cache_lock:
            hit=self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key); return hit
        found=[]
        if not terms: found=self.links[:max_results]
        else:
            for url,raw,clean in self._records:
                if self._record_matches(raw,clean,terms):
                    found.append(url)
                    if len(found)>=max_results:break
        if self.db is not None and terms and len(found)<max_results:
            try:
                # Managed Link Library is searched in addition to legacy text lists.
                # guild scoping is supplied by search(..., guild_id=...).
                pass
            except Exception:
                pass
        with self._cache_lock:
            self._cache[key]=found
            self._cache.move_to_end(key)
            while len(self._cache)>128:self._cache.popitem(last=False)
        return found
    def search(self,query:str,page:int=1,page_size:int=5,max_results:int=250,guild_id:int|None=None):
        matches=list(self._results(query,max_results))
        if self.db is not None and guild_id is not None:
            terms=[t for t in query.strip().split() if t]
            try:
                if terms:
                    fts=' AND '.join('\"'+t.replace('\"','')+'\"*' for t in terms)
                    rows=self.db.all('SELECT l.url FROM link_fts f JOIN links l ON l.id=f.link_id WHERE f.guild_id=? AND link_fts MATCH ? LIMIT ?', (guild_id,fts,max_results))
                else:
                    rows=self.db.all('SELECT url FROM links WHERE guild_id=? ORDER BY id DESC LIMIT ?',(guild_id,max_results))
                seen=set(matches)
                for r in rows:
                    if r['url'] not in seen:matches.append(r['url']);seen.add(r['url'])
                    if len(matches)>=max_results:break
            except Exception:
                pass
        total=len(matches);pages=max(1,math.ceil(total/page_size));page=max(1,min(page,pages));start=(page-1)*page_size
        return LinkPage(matches[start:start+page_size],page,page_size,total)
