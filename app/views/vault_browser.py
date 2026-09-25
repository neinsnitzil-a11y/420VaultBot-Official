from __future__ import annotations
import asyncio, shutil, tempfile
from pathlib import Path
import discord
from app.views.paginator import fmt_bytes

class VaultSearchModal(discord.ui.Modal,title='Search Physical Vault'):
 query=discord.ui.TextInput(label='Search the Vault',placeholder='e.g. serum, omnisphere, drumkit, midi',min_length=1,max_length=100)
 def __init__(self,view):super().__init__();self.v=view
 async def on_submit(self,i):
  self.v.query=str(self.query).strip();self.v.page=1;await i.response.defer();await self.v.async_refresh();await i.edit_original_response(embed=self.v.embed(),view=self.v)

class VaultResultSelect(discord.ui.Select):
 def __init__(self,view):
  self.v=view; r=view.result()
  opts=[]
  for n,x in enumerate(r.items,1+(r.page-1)*r.page_size):
   kind='Folder' if x.get('kind')=='folder' else 'File'; size=fmt_bytes(x.get('file_size') or 0)
   opts.append(discord.SelectOption(label=f'{n}. {x["filename"]}'[:100],description=f'{kind} • {size} • {(x.get("folder") or "/")}'[:100],value=f'{x.get("kind","file")}:{x["id"]}',emoji='📁' if kind=='Folder' else '💿'))
  super().__init__(placeholder='Select a Vault result to download…',options=opts or [discord.SelectOption(label='No results',value='none')],disabled=not bool(opts),row=1)
 async def callback(self,i):
  if self.values[0]=='none':return
  kind,item_id=self.values[0].split(':',1);await self.v.deliver(i,kind,int(item_id))

class VaultAudioView(discord.ui.View):
 def __init__(self,parent,row):super().__init__(timeout=300);self.parent=parent;self.row=row
 async def interaction_check(self,i):
  if i.user.id!=self.parent.owner_id:await i.response.send_message('This preview belongs to another user.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Preview Audio',emoji='🔊',style=discord.ButtonStyle.primary)
 async def preview(self,i,b):
  await i.response.defer(thinking=True);p=Path(self.row['full_path']);limit=i.guild.filesize_limit if i.guild else 10*1024*1024
  if not await asyncio.to_thread(p.is_file):return await i.followup.send('Audio source is currently offline. The index was preserved; reconnect storage and scan changes.')
  size=await asyncio.to_thread(lambda:p.stat().st_size)
  if size<=limit:return await i.followup.send(content=f'🔊 **Preview — {p.name}**',file=discord.File(p,filename=p.name))
  # Large source: create a short compressed preview when ffmpeg is installed.
  import subprocess, os
  if not shutil.which('ffmpeg'):return await i.followup.send('This audio file is too large for Discord preview and FFmpeg is not installed on the bot computer.')
  temp=tempfile.mkdtemp(prefix='420preview_');out=Path(temp)/'preview.mp3'
  try:
   def make():return subprocess.run(['ffmpeg','-y','-loglevel','error','-i',str(p),'-t','30','-vn','-b:a','128k',str(out)],capture_output=True,text=True,timeout=90)
   r=await asyncio.to_thread(make)
   if r.returncode or not out.is_file():return await i.followup.send('Could not generate this audio preview.')
   await i.followup.send(content=f'🔊 **30-second preview — {p.name}**',file=discord.File(out,filename=f'{p.stem}_preview.mp3'))
  finally:await asyncio.to_thread(shutil.rmtree,temp,True)
 @discord.ui.button(label='Download Original',emoji='📦',style=discord.ButtonStyle.secondary)
 async def download(self,i,b):await self.parent.deliver(i,'file',int(self.row['id']),audio_actions=False)

class VaultSearchView(discord.ui.View):
 def __init__(self,bot,owner_id,guild_id,page_size,max_results,query=''):
  super().__init__(timeout=600);self.bot=bot;self.owner_id=owner_id;self.guild_id=guild_id;self.page_size=max(1,min(int(page_size),20));self.max_results=max_results;self.query=query.strip();self.page=1;self._result=None;self.refresh()
 def result(self):
  if self._result is None:self._result=self.bot.search.search(self.query,self.page,self.page_size,None,self.max_results,self.guild_id)
  return self._result
 def refresh(self):
  self._result=self.bot.search.search(self.query,self.page,self.page_size,None,self.max_results,self.guild_id);self.page=self._result.page
  for c in list(self.children):
   if isinstance(c,VaultResultSelect):self.remove_item(c)
  self.add_item(VaultResultSelect(self))
  self.prev.disabled=self.page<=1;self.next.disabled=self.page>=self._result.pages
 async def async_refresh(self):
  self._result=await asyncio.to_thread(self.bot.search.search,self.query,self.page,self.page_size,None,self.max_results,self.guild_id);self.page=self._result.page
  for c in list(self.children):
   if isinstance(c,VaultResultSelect):self.remove_item(c)
  self.add_item(VaultResultSelect(self));self.prev.disabled=self.page<=1;self.next.disabled=self.page>=self._result.pages
 def embed(self):
  r=self.result();q=discord.utils.escape_markdown(self.query) if self.query else 'Press **Search Vault** to enter a query'
  e=discord.Embed(title='💾 420Vault — Physical Vault Browser',description=f'**Search:** {q}\n**Source:** Indexed physical Vault files and folders\n\nSelect a result below to download it. Internal database IDs stay hidden from the normal workflow.')
  if not self.query:e.add_field(name='Ready',value='Press **Search Vault** to open the search bar.',inline=False)
  elif not r.items:e.add_field(name='No results',value='Try fewer or broader keywords.',inline=False)
  else:
   start=1+(r.page-1)*r.page_size
   for n,x in enumerate(r.items,start):
    icon='📁' if x.get('kind')=='folder' else '💿'; size='Folder' if x.get('kind')=='folder' else fmt_bytes(x.get('file_size') or 0)
    e.add_field(name=f'{n}. {icon} {x["filename"]}'[:256],value=f'{size} • `{x.get("folder") or "/"}`'[:1024],inline=False)
  e.set_footer(text=f'Page {r.page}/{r.pages} • {r.total:,} result(s) • Physical Vault only');return e
 async def interaction_check(self,i):
  if i.user.id!=self.owner_id:await i.response.send_message('This Vault browser belongs to another user. Run `420_vault_search` for your own.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Search Vault',emoji='🔎',style=discord.ButtonStyle.primary,row=0)
 async def search(self,i,b):await i.response.send_modal(VaultSearchModal(self))
 @discord.ui.button(label='Previous',emoji='◀️',style=discord.ButtonStyle.secondary,row=0)
 async def prev(self,i,b):
  self.page=max(1,self.page-1);await i.response.defer();await self.async_refresh();await i.edit_original_response(embed=self.embed(),view=self)
 @discord.ui.button(label='Next',emoji='▶️',style=discord.ButtonStyle.secondary,row=0)
 async def next(self,i,b):
  self.page=min(self.result().pages,self.page+1);await i.response.defer();await self.async_refresh();await i.edit_original_response(embed=self.embed(),view=self)
 @discord.ui.button(label='Close',emoji='✖️',style=discord.ButtonStyle.danger,row=0)
 async def close(self,i,b):self.stop();await i.response.edit_message(view=None)
 async def deliver(self,i,kind,item_id,audio_actions=True):
  # A removable drive can pause Windows for seconds. Acknowledge Discord before
  # touching SQLite or the filesystem, then perform validation in worker threads.
  await i.response.defer(thinking=True)
  s=await asyncio.to_thread(self.bot.db.guild,self.guild_id)
  if not s.get('downloads_enabled',1):return await i.followup.send('Downloads are disabled by an administrator.')
  table='vault_folders' if kind=='folder' else 'vault_files';r=await asyncio.to_thread(self.bot.db.one,f'SELECT * FROM {table} WHERE guild_id=? AND id=?',(self.guild_id,item_id))
  if not r:return await i.followup.send('That indexed Vault item no longer exists. Ask an admin to scan the Vault again.')
  if audio_actions and kind=='file' and str(r['extension']).lower() in {'wav','wave','aif','aiff','flac','mp3','ogg','m4a','aac','wma'}:
   return await i.followup.send(f'🎵 **{r["filename"]}**\nChoose preview or original download:',view=VaultAudioView(self,r))
  def validate():
   base=Path(s.get('vault_path') or '').expanduser().resolve();p=Path(r['full_path']).expanduser().resolve();inside=(p==base or base in p.parents);base_ok=base.is_dir();item_ok=p.is_dir() if kind=='folder' else p.is_file();return base,p,inside,base_ok,item_ok
  base,p,inside,base_ok,item_ok=await asyncio.to_thread(validate);limit=i.guild.filesize_limit if i.guild else 10*1024*1024
  if not base_ok or not inside:return await i.followup.send('Vault path validation failed. Delivery blocked.')
  if not item_ok:return await i.followup.send('The physical Vault item is unavailable. Reconnect the drive and scan changes.')
  temp=None
  try:
   sendp=p
   if kind=='folder':
    stats=await asyncio.to_thread(self.bot.db.one,"SELECT COUNT(*) n,COALESCE(SUM(file_size),0) size FROM vault_files WHERE guild_id=? AND (folder=? OR folder LIKE ?)",(self.guild_id,r['relative_path'],r['relative_path'].rstrip('/')+'/%'))
    if stats and stats['size']>limit:return await i.followup.send(f'⚠️ This folder contains about **{fmt_bytes(stats["size"])}**, above this server upload limit (**{fmt_bytes(limit)}**).')
    if stats and stats['n']>10000:return await i.followup.send('⚠️ This folder contains more than 10,000 indexed files, so archive creation was blocked.')
    temp=tempfile.mkdtemp(prefix='420vault_');archive=await asyncio.to_thread(shutil.make_archive,str(Path(temp)/p.name),'zip',p.parent,p.name);sendp=Path(archive)
   size=await asyncio.to_thread(lambda:sendp.stat().st_size)
   if size>limit:return await i.followup.send(f'⚠️ **Too large for Discord upload.**\nItem: **{fmt_bytes(size)}**\nServer limit: **{fmt_bytes(limit)}**')
   await i.followup.send(content=f'📦 **{p.name}**',file=discord.File(sendp,filename=sendp.name))
  finally:
   if temp:await asyncio.to_thread(shutil.rmtree,temp,True)

