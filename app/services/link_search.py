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
        self.sources:list[Path]=[]; self._cache=OrderedDict(); self._cache_lock=threading.Lock(); self._site_counts={}; self.reload()
    def discover(self):
        # One authoritative discovery path for legacy + scraper-generated list parts.
        # Supports list(s).txt, lists_part_N.txt and links_part_N.txt in root, legacy,
        # and data/link_lists. This removes the old hard-coded part 1-4 ceiling.
        from app.services.link_library import LinkLibrary
        return LinkLibrary.bundled_list_files()
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
        # Precompute domains once during reload instead of reparsing every URL on every click.
        counts={}
        for u in out:
            try: h=(urlparse(u).hostname or '').lower().removeprefix('www.')
            except Exception: h=''
            if h: counts[h]=counts.get(h,0)+1
        self._site_counts=counts
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
    @staticmethod
    def _parse_query(query:str):
        raw=[t for t in query.lower().split() if t]
        site=''
        terms=[]
        for t in raw:
            if t.startswith('site:') and len(t)>5:
                site=t[5:].strip().lower().removeprefix('www.')
            else: terms.append(t)
        return tuple(terms),site
    @staticmethod
    def _site_match(url:str,site:str):
        if not site:return True
        host=(urlparse(url).hostname or '').lower().removeprefix('www.')
        return host==site or host.endswith('.'+site)
    def _results(self,query:str,max_results:int):
        terms,site=self._parse_query(query); key=(terms,site,max_results)
        with self._cache_lock:
            hit=self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key); return hit
        found=[]
        if not terms:
            found=[u for u in self.links if self._site_match(u,site)][:max_results]
        else:
            for url,raw,clean in self._records:
                if self._site_match(url,site) and self._record_matches(raw,clean,terms):
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
            terms,site=self._parse_query(query)
            try:
                if terms:
                    fts=' AND '.join('\"'+t.replace('\"','')+'\"*' for t in terms)
                    if site:
                        rows=self.db.all('SELECT l.url FROM link_fts f JOIN links l ON l.id=f.link_id WHERE f.guild_id=? AND link_fts MATCH ? AND (lower(l.domain)=? OR lower(l.domain) LIKE ?) LIMIT ?', (guild_id,fts,site,'%.'+site,max_results))
                    else:
                        rows=self.db.all('SELECT l.url FROM link_fts f JOIN links l ON l.id=f.link_id WHERE f.guild_id=? AND link_fts MATCH ? LIMIT ?', (guild_id,fts,max_results))
                else:
                    if site:
                        rows=self.db.all('SELECT url FROM links WHERE guild_id=? AND (lower(domain)=? OR lower(domain) LIKE ?) ORDER BY id DESC LIMIT ?',(guild_id,site,'%.'+site,max_results))
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

    def available_sites(self,guild_id:int|None=None,limit:int=500):
        counts=dict(self._site_counts)
        if self.db is not None and guild_id is not None:
            try:
                rows=self.db.all('SELECT lower(domain) domain,COUNT(*) n FROM links WHERE guild_id=? AND domain IS NOT NULL AND domain<>\'\' GROUP BY lower(domain)',(guild_id,))
                for r in rows:
                    h=(r['domain'] or '').removeprefix('www.')
                    if h: counts[h]=max(counts.get(h,0),int(r['n'] or 0))
            except Exception: pass
        return sorted(counts.items(),key=lambda x:(-x[1],x[0]))[:limit]

    def search_site(self,site:str,query:str='',page:int=1,page_size:int=5,max_results:int=250,guild_id:int|None=None):
        site=site.strip().lower().replace('https://','').replace('http://','').split('/')[0].removeprefix('www.')
        q=('site:'+site+' '+query.strip()).strip()
        return self.search(q,page,page_size,max_results,guild_id)
