from __future__ import annotations
import asyncio, hashlib, shutil, tempfile
from pathlib import Path
import discord
from app.views.paginator import fmt_bytes
AUDIO_EXTS={'wav','mp3'}

class VaultSearchModal(discord.ui.Modal,title='Search Physical Vault'):
 query=discord.ui.TextInput(label='Search the Vault',placeholder='e.g. serum, omnisphere, drumkit, midi',min_length=1,max_length=100)
 def __init__(self,view):super().__init__();self.v=view
 async def on_submit(self,i):
  self.v.query=str(self.query).strip();self.v.page=1;self.v.selected=None;self.v.now_playing=None;await i.response.defer();await self.v.async_refresh();await i.edit_original_response(embed=self.v.embed(),view=self.v,attachments=[])

class VaultResultSelect(discord.ui.Select):
 def __init__(self,view):
  self.v=view;r=view.result();opts=[]
  for n,x in enumerate(r.items,1+(r.page-1)*r.page_size):
   kind='Folder' if x.get('kind')=='folder' else 'File';size=fmt_bytes(x.get('file_size') or 0);ext=str(x.get('extension') or '').lower();audio=kind=='File' and ext in AUDIO_EXTS
   opts.append(discord.SelectOption(label=f'{n}. {x["filename"]}'[:100],description=f'{"WAV/MP3 • click to play" if audio else kind} • {size} • {(x.get("folder") or "/")}'[:100],value=f'{x.get("kind","file")}:{x["id"]}',emoji='🔊' if audio else ('📁' if kind=='Folder' else '💿')))
  super().__init__(placeholder='🎧 Click a WAV/MP3 to audition it • other files select for download…',options=opts or [discord.SelectOption(label='No results',value='none')],disabled=not bool(opts),row=1)
 async def callback(self,i):
  if self.values[0]=='none':return
  kind,item_id=self.values[0].split(':',1);self.v.selected=(kind,int(item_id))
  row=await asyncio.to_thread(self.v.lookup,kind,int(item_id))
  if row and kind=='file' and str(row['extension']).lower() in AUDIO_EXTS:
   return await self.v.preview_audio(i,row)
  self.v.now_playing=None;await i.response.send_message('✅ Selected for download. This item is not playable audio.',ephemeral=True)

class VaultSearchView(discord.ui.View):
 def __init__(self,bot,owner_id,guild_id,page_size,max_results,query=''):
  super().__init__(timeout=600);self.bot=bot;self.owner_id=owner_id;self.guild_id=guild_id;self.page_size=max(1,min(int(page_size),20));self.max_results=max_results;self.query=query.strip();self.page=1;self._result=None;self.selected=None;self.now_playing=None;self.refresh()
 def result(self):
  if self._result is None:self._result=self.bot.search.search(self.query,self.page,self.page_size,None,self.max_results,self.guild_id)
  return self._result
 def lookup(self,kind,item_id):return self.bot.db.one(f'SELECT * FROM {"vault_folders" if kind=="folder" else "vault_files"} WHERE guild_id=? AND id=?',(self.guild_id,item_id))
 def refresh(self):
  self._result=self.bot.search.search(self.query,self.page,self.page_size,None,self.max_results,self.guild_id);self.page=self._result.page
  for c in list(self.children):
   if isinstance(c,VaultResultSelect):self.remove_item(c)
  self.add_item(VaultResultSelect(self));self.prev.disabled=self.page<=1;self.next.disabled=self.page>=self._result.pages
 async def async_refresh(self):
  self._result=await asyncio.to_thread(self.bot.search.search,self.query,self.page,self.page_size,None,self.max_results,self.guild_id);self.page=self._result.page
  for c in list(self.children):
   if isinstance(c,VaultResultSelect):self.remove_item(c)
  self.add_item(VaultResultSelect(self));self.prev.disabled=self.page<=1;self.next.disabled=self.page>=self._result.pages
 def embed(self):
  r=self.result();q=discord.utils.escape_markdown(self.query) if self.query else 'Press **Search Vault** to enter a query'
  e=discord.Embed(title='💾 420Vault — Physical Vault Browser',description=f'**Search:** {q}\n**Source:** Indexed physical Vault files and folders\n\n🎧 **Audition:** choose any **WAV/MP3** below and its Discord player is attached to this browser message immediately. No Preview button and no extra confirmation step.\n💿 **Presets/other files:** selectable for download only.')
  if not self.query:e.add_field(name='Ready',value='Press **Search Vault** to open the search bar.',inline=False)
  elif not r.items:e.add_field(name='No results',value='Try fewer or broader keywords.',inline=False)
  else:
   for n,x in enumerate(r.items,1+(r.page-1)*r.page_size):
    ext=str(x.get('extension') or '').lower();audio=x.get('kind')!='folder' and ext in AUDIO_EXTS;icon='🔊' if audio else ('📁' if x.get('kind')=='folder' else '💿');size='Folder' if x.get('kind')=='folder' else fmt_bytes(x.get('file_size') or 0);tag=' • 🎵 playable' if audio else ''
    e.add_field(name=f'{n}. {icon} {x["filename"]}'[:256],value=f'{size} • `{x.get("folder") or "/"}`{tag}'[:1024],inline=False)
  
  if self.now_playing:e.add_field(name='🎧 Now auditioning',value=discord.utils.escape_markdown(self.now_playing)[:1024],inline=False)
  e.set_footer(text=f'Page {r.page}/{r.pages} • {r.total:,} result(s) • v5.8.6 Audio Browser');return e
 async def interaction_check(self,i):
  if i.user.id!=self.owner_id:await i.response.send_message('This Vault browser belongs to another user. Run `420_vault_search` for your own.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Search Vault',emoji='🔎',style=discord.ButtonStyle.primary,row=0)
 async def search(self,i,b):await i.response.send_modal(VaultSearchModal(self))
 @discord.ui.button(label='Previous',emoji='◀️',style=discord.ButtonStyle.secondary,row=0)
 async def prev(self,i,b):self.page=max(1,self.page-1);self.selected=None;self.now_playing=None;await i.response.defer();await self.async_refresh();await i.edit_original_response(embed=self.embed(),view=self,attachments=[])
 @discord.ui.button(label='Next',emoji='▶️',style=discord.ButtonStyle.secondary,row=0)
 async def next(self,i,b):self.page=min(self.result().pages,self.page+1);self.selected=None;self.now_playing=None;await i.response.defer();await self.async_refresh();await i.edit_original_response(embed=self.embed(),view=self,attachments=[])
 @discord.ui.button(label='Download Original / Selected',emoji='⬇️',style=discord.ButtonStyle.success,row=2)
 async def download_selected(self,i,b):
  if not self.selected:return await i.response.send_message('Select a Vault result first.',ephemeral=True)
  await self.deliver(i,*self.selected)
 @discord.ui.button(label='Close',emoji='✖️',style=discord.ButtonStyle.danger,row=2)
 async def close(self,i,b):self.stop();await i.response.edit_message(view=None)
 async def _preview_path(self,r,limit):
  """Return a playable Path for WAV/MP3, generating a short MP3 only when needed."""
  s=await asyncio.to_thread(self.bot.db.guild,self.guild_id)
  if not s.get('audio_preview_enabled',1):return None
  p=Path(r['full_path'])
  if not await asyncio.to_thread(p.is_file):return None
  size=await asyncio.to_thread(lambda:p.stat().st_size)
  if size<=limit:return p
  if not shutil.which('ffmpeg'):return None
  seconds=max(5,min(int(s.get('audio_preview_seconds') or 30),120));bitrate=max(64,min(int(s.get('audio_preview_bitrate') or 128),320))
  cache=Path(__file__).resolve().parents[2]/'data'/'preview_cache';cache.mkdir(parents=True,exist_ok=True)
  key=hashlib.sha256(f'{p}|{p.stat().st_mtime_ns}|{seconds}|{bitrate}'.encode()).hexdigest();out=cache/f'{key}.mp3'
  if not out.is_file():
   import subprocess
   def make():return subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(p),'-t',str(seconds),'-vn','-b:a',f'{bitrate}k',str(out)],capture_output=True,text=True,timeout=120)
   rr=await asyncio.to_thread(make)
   if rr.returncode or not out.is_file():return None
  return out if out.stat().st_size<=limit else None
 async def auto_preview_file(self,limit):
  """Load the first WAV/MP3 on the current result page into Discord's player."""
  for x in self.result().items:
   if x.get('kind')!='folder' and str(x.get('extension') or '').lower() in AUDIO_EXTS:
    row=await asyncio.to_thread(self.lookup,'file',int(x['id']))
    if row:
     p=await self._preview_path(row,limit)
     if p:return discord.File(p,filename=p.name)
  return None
 async def preview_audio(self,i,r):
  # One click auditions WAV/MP3. Discord renders native audio attachments outside the embed body,
  # but this edits the existing browser message instead of posting a second preview message.
  await i.response.defer()
  limit=i.guild.filesize_limit if i.guild else 10*1024*1024
  p=await self._preview_path(r,limit)
  if not p:return await i.followup.send('This WAV/MP3 cannot be auditioned right now (source offline, previews disabled, or it exceeds the upload limit without FFmpeg).',ephemeral=True)
  self.now_playing=str(r['filename']);await i.edit_original_response(embed=self.embed(),view=self,attachments=[discord.File(p,filename=p.name)])
 async def deliver(self,i,kind,item_id):
  await i.response.defer(thinking=True);s=await asyncio.to_thread(self.bot.db.guild,self.guild_id)
  if not s.get('downloads_enabled',1):return await i.followup.send('Downloads are disabled by an administrator.')
  r=await asyncio.to_thread(self.lookup,kind,item_id)
  if not r:return await i.followup.send('That indexed Vault item no longer exists.')
  def validate():
   base=Path(s.get('vault_path') or '').expanduser().resolve();p=Path(r['full_path']).expanduser().resolve();return base,p,(p==base or base in p.parents),base.is_dir(),(p.is_dir() if kind=='folder' else p.is_file())
  base,p,inside,base_ok,item_ok=await asyncio.to_thread(validate);limit=i.guild.filesize_limit if i.guild else 10*1024*1024
  if not base_ok or not inside:return await i.followup.send('Vault path validation failed. Delivery blocked.')
  if not item_ok:return await i.followup.send('The physical Vault item is unavailable. Reconnect the drive and scan changes.')
  temp=None
  try:
   sendp=p
   if kind=='folder':
    stats=await asyncio.to_thread(self.bot.db.one,"SELECT COUNT(*) n,COALESCE(SUM(file_size),0) size FROM vault_files WHERE guild_id=? AND (folder=? OR folder LIKE ?)",(self.guild_id,r['relative_path'],r['relative_path'].rstrip('/')+'/%'))
    if stats and stats['size']>limit:return await i.followup.send(f'⚠️ Folder about **{fmt_bytes(stats["size"])}**, above server upload limit (**{fmt_bytes(limit)}**).')
    temp=tempfile.mkdtemp(prefix='420vault_');sendp=Path(await asyncio.to_thread(shutil.make_archive,str(Path(temp)/p.name),'zip',p.parent,p.name))
   size=await asyncio.to_thread(lambda:sendp.stat().st_size)
   if size>limit:return await i.followup.send(f'⚠️ **Too large for Discord upload.**\nItem: **{fmt_bytes(size)}**\nServer limit: **{fmt_bytes(limit)}**')
   await i.followup.send(content=f'📦 **{p.name}**',file=discord.File(sendp,filename=sendp.name))
  finally:
   if temp:await asyncio.to_thread(shutil.rmtree,temp,True)
