from __future__ import annotations
import asyncio, html, re, threading, socket, ipaddress
from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

@dataclass
class LinkPreview:
    url:str
    title:str=''
    description:str=''
    image:str=''

class LinkPreviewService:
    def __init__(self, max_cache:int=512):
        self.max_cache=max_cache; self._cache=OrderedDict(); self._lock=threading.Lock()
    def _fetch(self,url:str)->LinkPreview:
        with self._lock:
            hit=self._cache.get(url)
            if hit is not None:self._cache.move_to_end(url);return hit
        p=LinkPreview(url=url)
        try:
            parsed=urlparse(url)
            if parsed.scheme not in ('http','https') or not parsed.hostname:return p
            try:
                for info in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme=='https' else 80), type=socket.SOCK_STREAM):
                    ip=ipaddress.ip_address(info[4][0])
                    if not ip.is_global:return p
            except (socket.gaierror,ValueError):return p
            req=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; 420VaultBot/2.2; +Discord preview)'})
            with urlopen(req,timeout=3) as r:
                ctype=(r.headers.get('Content-Type') or '').lower()
                if 'text/html' not in ctype:return p
                raw=r.read(524288).decode('utf-8','ignore')
            def meta(*names):
                for name in names:
                    pats=[rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)',rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']{re.escape(name)}["\']']
                    for pat in pats:
                        m=re.search(pat,raw,re.I)
                        if m:return html.unescape(m.group(1).strip())
                return ''
            p.title=meta('og:title','twitter:title')
            if not p.title:
                m=re.search(r'<title[^>]*>(.*?)</title>',raw,re.I|re.S);p.title=html.unescape(re.sub(r'\s+',' ',m.group(1)).strip()) if m else ''
            p.description=meta('og:description','twitter:description','description')[:300]
            img=meta('og:image','og:image:url','twitter:image','twitter:image:src')
            if img:p.image=urljoin(url,img)
        except Exception:pass
        with self._lock:
            self._cache[url]=p;self._cache.move_to_end(url)
            while len(self._cache)>self.max_cache:self._cache.popitem(last=False)
        return p
    async def get_many(self,urls:list[str]):
        return await asyncio.gather(*(asyncio.to_thread(self._fetch,u) for u in urls))
