from __future__ import annotations
import asyncio, math, tempfile, shutil
from dataclasses import dataclass
from urllib.parse import urlparse,unquote
import discord

@dataclass
class CombinedPage:
 items:list; page:int; page_size:int; total:int
 @property
 def pages(self):return max(1,math.ceil(self.total/self.page_size))

class SearchModal(discord.ui.Modal,title='Search 420Vault'):
 query=discord.ui.TextInput(label='Search',placeholder='e.g. omnisphere, Jay Cactus, serum trap',min_length=1,max_length=100)
 def __init__(self,view):super().__init__();self.v=view
 async def on_submit(self,i):
  self.v.query=str(self.query).strip();self.v.page=1;await i.response.defer();await self.v.load();await self.v.edit_interaction(i)


class SiteSearchModal(discord.ui.Modal,title='Search Links by Website'):
 site=discord.ui.TextInput(label='Website / domain',placeholder='example.com',max_length=200)
 query=discord.ui.TextInput(label='Optional keywords',placeholder='serum, omnisphere, drum kit...',required=False,max_length=100)
 source=discord.ui.TextInput(label='Source: library, live, or both',placeholder='both',default='both',required=False,max_length=10)
 def __init__(self,view):super().__init__();self.v=view
 async def on_submit(self,i):
  clean=str(self.site).strip().lower().replace('https://','').replace('http://','').split('/')[0].lstrip('www.')
  if not clean or '.' not in clean:return await i.response.send_message('Enter a domain such as `example.com`.',ephemeral=True)
  self.v.site_domain=clean; self.v.site_terms=str(self.query).strip(); mode=str(self.source).strip().lower() or 'both'; self.v.source_mode=mode if mode in ('library','live','both') else 'both'; self.v.query=('site:'+clean+' '+self.v.site_terms).strip();self.v.page=1;await i.response.defer();await self.v.load();await self.v.edit_interaction(i)

class SendVaultItemModal(discord.ui.Modal,title='Send Vault Item'):
 item=discord.ui.TextInput(label='Vault item ID',placeholder='F123 for a file or D45 for a folder',max_length=20)
 def __init__(self,view):super().__init__();self.v=view
 async def on_submit(self,i):
  raw=str(self.item).strip().upper();kind='folder' if raw.startswith('D') else 'file';num=raw[1:] if raw[:1] in ('D','F') else raw
  if not num.isdigit():return await i.response.send_message('Use an item ID such as `F123` or `D45`.',ephemeral=True)
  await i.response.defer(thinking=True,ephemeral=True)
  table='vault_folders' if kind=='folder' else 'vault_files';r=self.v.bot.db.one(f'SELECT * FROM {table} WHERE guild_id=? AND id=?',(self.v.guild_id,int(num)))
  if not r:return await i.followup.send('That Vault item was not found in this server index.',ephemeral=True)
  settings=self.v.bot.db.guild(self.v.guild_id)
  if not settings.get('downloads_enabled',1):return await i.followup.send('Downloads are disabled by an administrator.',ephemeral=True)
  ent=self.v.bot.subscriptions.entitlement_for(self.v.guild_id,i.user.id) if settings.get('licensing_enabled',1) else {'id':None}
  if settings.get('licensing_enabled',1) and (not ent or not self.v.bot.db.one("SELECT 1 FROM licenses WHERE guild_id=? AND user_id=? AND entitlement_id=? AND status='active'",(self.v.guild_id,i.user.id,ent['id']))):return await i.followup.send('Your 420Vault access is no longer active.',ephemeral=True)
  from pathlib import Path
  def _validate_paths():
   base=Path(settings.get('vault_path') or '').expanduser().resolve();p=Path(r['full_path']).expanduser().resolve()
   inside=(p==base or base in p.parents);exists=p.exists();correct=p.is_dir() if kind=='folder' else p.is_file();base_ok=base.is_dir()
   return base,p,inside,exists,correct,base_ok
  base,p,inside,exists,correct,base_ok=await asyncio.to_thread(_validate_paths);limit=i.guild.filesize_limit if i.guild else 10*1024*1024
  if not base_ok or not inside:return await i.followup.send('Vault path validation failed. Delivery blocked.',ephemeral=True)
  if not correct:return await i.followup.send('Indexed Vault item is no longer available in the expected form.',ephemeral=True)
  if not exists:return await i.followup.send('🔴 The physical Vault item is currently unavailable. Reconnect the drive and run **Scan Changes**.',ephemeral=True)
  temp=None
  try:
   sendp=p
   if kind=='folder':
    stats=self.v.bot.db.one("SELECT COUNT(*) n,COALESCE(SUM(file_size),0) size FROM vault_files WHERE guild_id=? AND (folder=? OR folder LIKE ?)",(self.v.guild_id,r['relative_path'],r['relative_path'].rstrip('/')+'/%'))
    if stats and stats['size']>limit:return await i.followup.send(f'⚠️ Indexed folder contents are **{fmt_bytes(stats["size"])}**, already above this server upload limit (**{fmt_bytes(limit)}**). Archive creation was skipped.')
    if stats and stats['n']>10000:return await i.followup.send('⚠️ Folder contains more than 10,000 indexed files. Archive creation was blocked by the resource limit.')
    td=tempfile.mkdtemp(prefix='420vault_');temp=td;archive=await asyncio.to_thread(shutil.make_archive,str(__import__('pathlib').Path(td)/p.name),'zip',p.parent,p.name);sendp=__import__('pathlib').Path(archive)
   size=await asyncio.to_thread(lambda:sendp.stat().st_size)
   if size>limit:return await i.followup.send(f'⚠️ **Too large for this Discord destination.**\nItem: **{fmt_bytes(size)}**\nCurrent server upload limit: **{fmt_bytes(limit)}**\nOver by: **{fmt_bytes(size-limit)}**')
   await i.followup.send(file=discord.File(sendp,filename=sendp.name))
  finally:
   if temp:shutil.rmtree(temp,ignore_errors=True)

class UnifiedSearchView(discord.ui.View):
 def __init__(self,bot,owner_id,page_size,max_results,query='',guild_id=0):
  super().__init__(timeout=600);self.bot=bot;self.owner_id=owner_id;self.guild_id=guild_id;self.page_size=page_size;self.max_results=max_results;self.query=query;self.page=1;self._result=None;self._previews=[];self._all=[];self.site_domain='';self.site_terms='';self.source_mode='library'
 async def load(self):
  q=self.query;cap=self.max_results
  def gather_library():
   links=self.bot.link_search.search(q,1,cap,cap,self.guild_id).items
   return links[:cap]
  library=await asyncio.to_thread(gather_library) if self.source_mode in ('library','both') else []
  live=[]
  if self.site_domain and self.source_mode in ('live','both'):
   live=await self.bot.live_web_search.search_site(self.site_domain,self.site_terms,cap)
  merged=[];seen=set();libset=set(library);liveset=set(live)
  for u in library+live:
   if u in seen:continue
   seen.add(u); src='both' if u in libset and u in liveset else ('library' if u in libset else 'live')
   merged.append({'kind':'link','url':u,'source':src})
   if len(merged)>=cap:break
  # Never present a URL already known-malicious from a prior administrator AV scan.
  # This does not submit search results to an external service; it only uses cached local verdicts.
  bad=[];filtered=[]
  for item in merged:
   if item.get('kind')=='link':
    row=await asyncio.to_thread(self.bot.db.one,"SELECT verdict FROM link_av_results WHERE guild_id=? AND url=? ORDER BY id DESC LIMIT 1",(self.guild_id,item['url']))
    if row and row['verdict']=='malicious':bad.append(item['url']);continue
   filtered.append(item)
  merged=filtered
  if bad:
   try:
    from app.views.support_tickets import create_support_ticket
    guild=self.bot.get_guild(self.guild_id);member=guild.get_member(self.owner_id) if guild else None
    if guild and member:
     await create_support_ticket(self.bot,guild,member,'security','Known malicious link blocked from search','420VaultBot blocked locally cached malicious link(s) from search results. No external AV request was made during this search. Admin review/removal is required.\n\n'+'\n'.join(bad[:40]))
   except Exception:pass
  self._all=merged;total=len(self._all);pages=max(1,math.ceil(total/self.page_size));self.page=max(1,min(self.page,pages));start=(self.page-1)*self.page_size
  items=self._all[start:start+self.page_size];self._result=CombinedPage(items,self.page,self.page_size,total)
  urls=[x['url'] for x in items];self._previews=await self.bot.link_preview.get_many(urls) if urls else []
  return self._result
 def native_content(self):
  # Keep the browser clean: preview metadata/images are rendered in embeds.
  # Raw URLs are intentionally not dumped above the browser.
  return None
 def embeds(self):
  e=discord.Embed(title='🔎 420Vault Search Browser',description=f'**Search:** `{discord.utils.escape_markdown(self.query) if self.query else "Press Search to enter a query"}`\n**Source:** {self.source_mode.title() if self.site_domain else "Link Library"}\n\n⚠️ **THIRD-PARTY LINK SECURITY**\nLinks shown by 420VaultBot can lead to third-party websites, redirects, file hosts, or downloads that 420VaultBot does not control. A search result or a Link AV result with **NO DETECTIONS** does **not** guarantee that a destination is safe.\n\n🛡️ **You are responsible for protecting your device.** Keep your browser, operating system, antivirus/security software, and security features up to date. Check unfamiliar URLs with a reputable URL scanner before opening them and pay attention to the final destination after redirects. **Never disable antivirus, browser protection, SmartScreen, Gatekeeper, or another security feature because a website or download tells you to.**\n\n🚨 If a link redirects somewhere unexpected, triggers a security warning, looks suspicious, or appears malicious, **do not continue to the download. Report the link to server staff so it can be investigated and removed.**')
  if not self.query:e.add_field(name='Ready',value='Press **Search** and type what you want. Results come from the managed Link Library. For physical files, use `420_vault_search`.',inline=False);return [e]
  r=self._result
  if not r or not r.items:e.add_field(name='No results',value='Try fewer or broader keywords.',inline=False);return [e]
  e.set_footer(text=f'Page {r.page}/{r.pages} • {r.total:,} result(s) • {self.page_size} per page')
  out=[e];pn=0;start=1+(r.page-1)*r.page_size
  from app.views.paginator import fmt_bytes
  for idx,item in enumerate(r.items):
   if item['kind']=='vault':
    x=item['data'];out.append(discord.Embed(title=f'{start+idx}. {"📁" if x.get("kind")=="folder" else "💿"} {x["filename"]}',description=f'Local Vault • `{"D" if x.get("kind")=="folder" else "F"}{x["id"]}` • {x.get("category","file")} • {fmt_bytes(x["file_size"])} • `{x["folder"] or "/"}`'))
   else:
    url=item['url'];pv=self._previews[pn] if pn<len(self._previews) else None;pn+=1
    path=unquote(urlparse(url).path.rstrip('/').split('/')[-1]) or urlparse(url).netloc;fallback=path.replace('-',' ').replace('_',' ')[:100]
    title=(pv.title if pv and pv.title else fallback)[:240];desc=(pv.description if pv and pv.description else 'Preview metadata was not available from this destination.')
    card=discord.Embed(title=f'{start+idx}. {"📚🌐" if item.get("source")=="both" else ("🌐" if item.get("source")=="live" else "📚")} {title}',url=url,description=desc[:400]);card.set_footer(text=urlparse(url).netloc)
    if pv and pv.image and pv.image.startswith(('http://','https://')):card.set_image(url=pv.image)
    out.append(card)
  return out[:10]
 async def edit_interaction(self,i):await i.edit_original_response(content=self.native_content(),embeds=self.embeds(),view=self)
 async def interaction_check(self,i):
  if i.user.id!=self.owner_id:await i.response.send_message('This search belongs to another user. Run `420_search` for your own.',ephemeral=True);return False
  if not await asyncio.to_thread(self.bot.auth.session_active,self.guild_id,i.user.id,True):await i.response.send_message('🔐 Your 420Vault session expired. Run `420_auth` to sign in again.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Search',emoji='🔎',style=discord.ButtonStyle.primary,row=0)
 async def search_button(self,i,b):await i.response.send_modal(SearchModal(self))
 @discord.ui.button(label='Search by Site',emoji='🌐',style=discord.ButtonStyle.success,row=1)
 async def site_search_button(self,i,b):await i.response.send_modal(SiteSearchModal(self))
 @discord.ui.button(label='Available Websites',emoji='📚',style=discord.ButtonStyle.secondary,row=1)
 async def available_sites(self,i,b):
  sites=await asyncio.to_thread(self.bot.link_search.available_sites,self.guild_id,100)
  if not sites:return await i.response.send_message('No websites are currently indexed in the Link Library.',ephemeral=True)
  lines=[f'`{d}` — **{n:,}** link(s)' for d,n in sites[:75]]
  chunks=[]
  while lines:
   cur=[];size=0
   while lines and size+len(lines[0])+1<3500:
    x=lines.pop(0);cur.append(x);size+=len(x)+1
   chunks.append('\n'.join(cur))
  embeds=[discord.Embed(title=f'📚 Available Link-Library Websites ({len(sites):,} shown)',description=c) for c in chunks[:5]]
  await i.response.send_message(embeds=embeds,ephemeral=True)
 @discord.ui.button(label='Previous',emoji='◀️',style=discord.ButtonStyle.secondary,row=0)
 async def prev(self,i,b):self.page=max(1,self.page-1);await i.response.defer();await self.load();await self.edit_interaction(i)
 @discord.ui.button(label='Next',emoji='▶️',style=discord.ButtonStyle.secondary,row=0)
 async def next(self,i,b):
  if self._result:self.page=min(self._result.pages,self.page+1)
  await i.response.defer();await self.load();await self.edit_interaction(i)
 @discord.ui.button(label='Close',emoji='✖️',style=discord.ButtonStyle.danger,row=0)
 async def close(self,i,b):self.stop();await i.response.edit_message(content=None,view=None)
