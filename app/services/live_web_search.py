from __future__ import annotations
import html,re
from urllib.parse import quote_plus,urlparse,parse_qs,unquote
import aiohttp

class LiveWebSearchService:
    """Small public-web search adapter used by Site Search.

    It searches public search-result pages and returns URLs only. It does not bypass
    authentication, CAPTCHAs, robots controls, or protected pages.
    """
    def __init__(self, timeout: int = 12):
        self.timeout=timeout
        self.headers={'User-Agent':'Mozilla/5.0 (compatible; 420VaultBot/6.0; +public-web-search)'}

    @staticmethod
    def _host_ok(url:str,domain:str)->bool:
        try: host=(urlparse(url).hostname or '').lower().removeprefix('www.')
        except Exception:return False
        d=domain.lower().removeprefix('www.')
        return host==d or host.endswith('.'+d)

    @staticmethod
    def _clean_ddg(href:str)->str:
        href=html.unescape(href)
        if href.startswith('//'): href='https:'+href
        try:
            q=parse_qs(urlparse(href).query)
            if 'uddg' in q:return unquote(q['uddg'][0])
        except Exception:pass
        return href

    async def search_site(self,domain:str,query:str='',limit:int=50)->list[str]:
        domain=domain.strip().lower().replace('https://','').replace('http://','').split('/')[0].removeprefix('www.')
        if not domain:return []
        term=f'site:{domain} {query}'.strip(); timeout=aiohttp.ClientTimeout(total=self.timeout)
        found=[];seen=set()
        # DuckDuckGo HTML endpoint: no API key required. Failure simply returns no live results.
        url='https://html.duckduckgo.com/html/?q='+quote_plus(term)
        try:
            async with aiohttp.ClientSession(timeout=timeout,headers=self.headers) as s:
                async with s.get(url,allow_redirects=True) as r:
                    if r.status!=200:return []
                    body=await r.text(errors='ignore')
            hrefs=re.findall(r'<a[^>]+class=["\'][^"\']*result__a[^"\']*["\'][^>]+href=["\']([^"\']+)',body,re.I)
            if not hrefs: hrefs=re.findall(r'href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*result__a',body,re.I)
            for h in hrefs:
                u=self._clean_ddg(h)
                if u.startswith(('http://','https://')) and self._host_ok(u,domain) and u not in seen:
                    seen.add(u);found.append(u)
                    if len(found)>=limit:break
        except Exception:return []
        return found
