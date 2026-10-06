from __future__ import annotations
import json, os
from urllib.parse import urlsplit, quote
import aiohttp

URLHAUS_REPO='https://github.com/abusech/URLhaus'
URLHAUS_API='https://urlhaus-api.abuse.ch/v1/url/'
METADEFENDER_API='https://api.metadefender.com/v4'
SECURITY_NOTICE=('420VaultBot link reputation is an aid, not a guarantee. Scraped/third-party links remain untrusted. '
                 'No-detection results do not prove a URL is safe. Administrators and users are responsible for learning '
                 'safe browsing practices and independently reviewing links before opening or distributing them.')

class LinkAV:
 def __init__(self,db):self.db=db
 def settings(self,gid):
  r=self.db.one('SELECT * FROM link_av_settings WHERE guild_id=?',(gid,))
  if r:return dict(r)
  uk=os.getenv('URLHAUS_AUTH_KEY','').strip();mk=os.getenv('METADEFENDER_API_KEY','').strip()
  return {'guild_id':gid,'enabled':1 if (uk or mk) else 0,'provider':'all','auth_key':uk,'follow_redirects':1,'metadefender_enabled':1 if mk else 0,'metadefender_api_key':mk}
 def save(self,gid,enabled,provider='all',auth_key='',follow_redirects=True,metadefender_enabled=False,metadefender_api_key=''):
  self.db.execute('INSERT INTO link_av_settings(guild_id,enabled,provider,auth_key,follow_redirects,metadefender_enabled,metadefender_api_key) VALUES(?,?,?,?,?,?,?) ON CONFLICT(guild_id) DO UPDATE SET enabled=excluded.enabled,provider=excluded.provider,auth_key=excluded.auth_key,follow_redirects=excluded.follow_redirects,metadefender_enabled=excluded.metadefender_enabled,metadefender_api_key=excluded.metadefender_api_key,updated_at=CURRENT_TIMESTAMP',(gid,1 if enabled else 0,provider,auth_key,1 if follow_redirects else 0,1 if metadefender_enabled else 0,metadefender_api_key))
 def enabled_providers(self,gid):
  s=self.settings(gid);out=[]
  if not s.get('enabled'):return out
  if s.get('auth_key'):out.append('urlhaus')
  if s.get('metadefender_enabled') and s.get('metadefender_api_key'):out.append('metadefender')
  return out
 def configured(self,gid):return bool(self.enabled_providers(gid))
 async def _lookup_urlhaus(self,key,url,session):
  try:
   async with session.post(URLHAUS_API,data={'url':url},headers={'Auth-Key':key},timeout=aiohttp.ClientTimeout(total=20)) as r:
    data=await r.json(content_type=None)
    if r.status>=400:return {'url':url,'provider':'urlhaus','verdict':'scan_error','detail':f'HTTP {r.status}'}
   q=data.get('query_status')
   if q=='ok':return {'url':url,'provider':'urlhaus','verdict':'malicious','detail':f'URLhaus match: {data.get("url_status","known")} / {data.get("threat","malware URL")}', 'raw':data}
   if q=='no_results':return {'url':url,'provider':'urlhaus','verdict':'no_detections','detail':'No URLhaus match'}
   return {'url':url,'provider':'urlhaus','verdict':'unknown','detail':str(q or 'unknown response')}
  except Exception as e:return {'url':url,'provider':'urlhaus','verdict':'scan_error','detail':f'{type(e).__name__}: {e}'}
 async def _lookup_metadefender(self,key,url,session):
  try:
   endpoint=f'{METADEFENDER_API}/url/{quote(url,safe="")}'
   async with session.get(endpoint,headers={'apikey':key},timeout=aiohttp.ClientTimeout(total=25)) as r:
    data=await r.json(content_type=None)
    if r.status==401:return {'url':url,'provider':'metadefender','verdict':'scan_error','detail':'Invalid MetaDefender API key'}
    if r.status==429:return {'url':url,'provider':'metadefender','verdict':'scan_error','detail':'MetaDefender rate limit exceeded'}
    if r.status>=400:return {'url':url,'provider':'metadefender','verdict':'scan_error','detail':f'HTTP {r.status}'}
   detected=data.get('detected_by',data.get('detected',0))
   try:detected=int(detected or 0)
   except Exception:detected=0
   # API responses may also expose verdict-like fields depending on reputation sources/account tier.
   blob=json.dumps(data).lower()
   if detected>0 or 'malicious' in blob:return {'url':url,'provider':'metadefender','verdict':'malicious','detail':f'MetaDefender reputation detections: {detected}', 'raw':data}
   if 'suspicious' in blob or 'likely_malicious' in blob:return {'url':url,'provider':'metadefender','verdict':'suspicious','detail':'MetaDefender reputation marked suspicious', 'raw':data}
   return {'url':url,'provider':'metadefender','verdict':'no_detections','detail':f'No MetaDefender reputation detections ({detected})','raw':data}
  except Exception as e:return {'url':url,'provider':'metadefender','verdict':'scan_error','detail':f'{type(e).__name__}: {e}'}
 async def _redirect_chain(self,url,session,max_hops=8):
  chain=[url]
  try:
   async with session.get(url,allow_redirects=True,timeout=aiohttp.ClientTimeout(total=20)) as r:chain=[str(x.url) for x in r.history]+[str(r.url)]
  except Exception:pass
  out=[]
  for u in chain[:max_hops+1]:
   if u not in out and urlsplit(u).scheme in ('http','https'):out.append(u)
  return out or [url]
 async def test_providers(self,gid):
  s=self.settings(gid);providers=self.enabled_providers(gid);results={}
  if not providers:return False,{'configuration':'No Link AV provider is enabled/configured.'}
  async with aiohttp.ClientSession(headers={'User-Agent':'420VaultBot-LinkSecurity/6.2.1'}) as session:
   if 'urlhaus' in providers:
    r=await self._lookup_urlhaus(s['auth_key'],'https://example.com/420vault-provider-healthcheck',session);results['URLhaus']=r['detail'] if r['verdict']!='scan_error' else 'ERROR: '+r['detail']
   if 'metadefender' in providers:
    try:
     async with session.get(f'{METADEFENDER_API}/apikey/',headers={'apikey':s['metadefender_api_key']},timeout=aiohttp.ClientTimeout(total=20)) as resp:
      if resp.status==200:
       rem=resp.headers.get('X-RateLimit-Remaining');results['MetaDefender']='Connected'+(f' • remaining: {rem}' if rem else '')
      else:results['MetaDefender']=f'ERROR: HTTP {resp.status}'
    except Exception as e:results['MetaDefender']=f'ERROR: {type(e).__name__}: {e}'
  return all(not str(v).startswith('ERROR:') for v in results.values()),results
 async def test_provider(self,gid):
  ok,res=await self.test_providers(gid);return ok,' | '.join(f'{k}: {v}' for k,v in res.items())
 async def scan_urls(self,gid,urls,progress=None):
  s=self.settings(gid);providers=self.enabled_providers(gid)
  if not providers:raise RuntimeError('Link AV is disabled or no provider API key is configured.')
  urls=list(dict.fromkeys(urls));results=[];order={'malicious':5,'suspicious':4,'scan_error':3,'unknown':2,'no_detections':0}
  async with aiohttp.ClientSession(headers={'User-Agent':'420VaultBot-LinkSecurity/6.2.1'}) as session:
   for n,url in enumerate(urls,1):
    chain=await self._redirect_chain(url,session) if s.get('follow_redirects') else [url];checked=[]
    for u in chain:
     if 'urlhaus' in providers:checked.append(await self._lookup_urlhaus(s['auth_key'],u,session))
     if 'metadefender' in providers:checked.append(await self._lookup_metadefender(s['metadefender_api_key'],u,session))
    overall=max(checked,key=lambda x:order.get(x['verdict'],2))['verdict'] if checked else 'unknown'
    result={'original_url':url,'verdict':overall,'chain':checked,'providers':providers};results.append(result)
    detail='; '.join(f'{x["provider"]}:{x["verdict"]}: {x["detail"]}' for x in checked)[:4000]
    self.db.execute('INSERT INTO link_av_results(guild_id,url,provider,verdict,detail,redirect_chain) VALUES(?,?,?,?,?,?)',(gid,url,'+'.join(providers),overall,detail,json.dumps([x['url'] for x in checked])))
    if progress and (n==1 or n%25==0 or n==len(urls)):await progress(n,len(urls),overall)
  return results
