from __future__ import annotations
import asyncio, math, tempfile, shutil
from pathlib import Path
from urllib.parse import quote
import discord
from app.views.paginator import fmt_bytes
from app.services.access import check_access

class DriveSearchModal(discord.ui.Modal,title='Search Google Drive'):
 query=discord.ui.TextInput(label='Search The Drive',placeholder='e.g. serum, drumkit, omnisphere',min_length=1,max_length=100)
 def __init__(self,v):super().__init__();self.v=v
 async def on_submit(self,i):
  self.v.query=str(self.query).strip();self.v.mode='search';self.v.page=1
  await i.response.defer()
  await self.v.async_refresh()
  await i.edit_original_response(embed=self.v.embed(),view=self.v.rebuild())

class DriveSelect(discord.ui.Select):
 def __init__(self,v):
  self.v=v;items,total=v.items();opts=[]
  for x in items[:25]:opts.append(discord.SelectOption(label=x['name'][:100],description=(('Folder' if x['is_folder'] else fmt_bytes(x['size'] or 0))+' • '+(x['relative_path'] or '/'))[:100],value=('a:'+str(x['archive_entry_id']) if x.get('archive_entry_id') else x['file_id']),emoji='📁' if x['is_folder'] else '☁️'))
  super().__init__(placeholder='Select a Google Drive result…',options=opts or [discord.SelectOption(label='No results',value='none')],disabled=not opts,row=1)
 async def callback(self,i):
  if self.values[0]!='none':await self.v.select(i,self.values[0])

class DriveBrowserView(discord.ui.View):
 """Drive browser with no SQLite work on Discord's event-loop thread."""
 def __init__(self,bot,owner_id,guild_id,page_size=5,max_results=250):
  super().__init__(timeout=600);self.bot=bot;self.owner_id=owner_id;self.guild_id=guild_id;self.page_size=min(max(1,page_size),20);self.max_results=max_results;self.page=1;self.query='';self.mode='browse';self.root='';self.parent='';self.stack=[];self._items=[];self._total=0;self._src=None
 def items(self):return self._items,self._total
 async def async_refresh(self):
  src=await asyncio.to_thread(self.bot.db.one,'SELECT * FROM drive_sources WHERE guild_id=?',(self.guild_id,));self._src=dict(src) if src else None
  if self._src and not self.root:self.root=self._src['root_file_id'];self.parent=self.root
  if not self._src:self._items=[];self._total=0;return self
  if self.mode=='search':items,total=await asyncio.to_thread(self.bot.google_drive.search,self.guild_id,self.query,self.page,self.page_size,self.max_results)
  else:items,total=await asyncio.to_thread(self.bot.google_drive.children,self.guild_id,self.parent,self.page,self.page_size)
  self._items,self._total=items,total
  pages=max(1,math.ceil(min(total,self.max_results)/self.page_size));self.page=max(1,min(self.page,pages));return self
 def rebuild(self):
  for c in list(self.children):
   if isinstance(c,DriveSelect):self.remove_item(c)
  self.add_item(DriveSelect(self));pages=max(1,math.ceil(min(self._total,self.max_results)/self.page_size));self.prev.disabled=self.page<=1;self.next.disabled=self.page>=pages;self.up.disabled=(self.mode=='browse' and self.parent==self.root);return self
 def embed(self):
  items,total=self.items();pages=max(1,math.ceil(min(total,self.max_results)/self.page_size));desc=f'**Connected root:** {self._src["root_name"] if self._src else "Not configured"}\n**Mode:** {"Search" if self.mode=="search" else "Folder browser"}'
  if self.query and self.mode=='search':desc+=f'\n**Search:** {discord.utils.escape_markdown(self.query)}'
  e=discord.Embed(title='☁️ 420Vault — Google Drive Browser',description=desc)
  if not items:e.add_field(name='No results',value='Search for something else or ask an admin to sync Google Drive.',inline=False)
  for n,x in enumerate(items,1+(self.page-1)*self.page_size):e.add_field(name=f'{n}. {"📁" if x["is_folder"] else "☁️"} {x["name"]}'[:256],value=f'{"Folder" if x["is_folder"] else fmt_bytes(x["size"] or 0)} • `{x["relative_path"] or "/"}`'[:1024],inline=False)
  e.set_footer(text=f'Page {self.page}/{pages} • {total:,} result(s) • Google Drive');return e
 async def interaction_check(self,i):
  if i.user.id!=self.owner_id:await i.response.send_message('This Google Drive browser belongs to another user. Run `420_drive_search` for your own.',ephemeral=True);return False
  state=await asyncio.to_thread(check_access,self.bot,i.guild,i.user)
  if not state.allowed:await i.response.send_message('Your 420Vault access is no longer active.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Search Drive',emoji='🔎',style=discord.ButtonStyle.primary,row=0)
 async def search(self,i,b):await i.response.send_modal(DriveSearchModal(self))
 @discord.ui.button(label='Previous',emoji='◀️',row=0)
 async def prev(self,i,b):
  self.page=max(1,self.page-1);await i.response.defer();await self.async_refresh();await i.edit_original_response(embed=self.embed(),view=self.rebuild())
 @discord.ui.button(label='Next',emoji='▶️',row=0)
 async def next(self,i,b):
  self.page+=1;await i.response.defer();await self.async_refresh();await i.edit_original_response(embed=self.embed(),view=self.rebuild())
 @discord.ui.button(label='Up / Home',emoji='⬆️',row=0)
 async def up(self,i,b):
  if self.mode=='search':self.mode='browse';self.parent=self.root;self.stack=[]
  elif self.stack:self.parent=self.stack.pop()
  else:self.parent=self.root
  self.page=1;await i.response.defer();await self.async_refresh();await i.edit_original_response(embed=self.embed(),view=self.rebuild())
 @discord.ui.button(label='Close',emoji='✖️',style=discord.ButtonStyle.danger,row=0)
 async def close(self,i,b):self.stop();await i.response.edit_message(view=None)
 async def select(self,i,fid):
  archive_hit=str(fid).startswith('a:')
  if archive_hit:
   eid=int(str(fid).split(':',1)[1]);a=await asyncio.to_thread(self.bot.db.one,'SELECT a.*,d.* FROM drive_archive_entries a JOIN drive_items d ON d.guild_id=a.guild_id AND d.file_id=a.archive_file_id WHERE a.guild_id=? AND a.id=? AND d.available=1',(self.guild_id,eid))
   if not a:return await i.response.send_message('That archive result is no longer indexed.',ephemeral=True)
   a=dict(a);r={'file_id':a['archive_file_id'],'name':a['archive_name'],'mime_type':a['mime_type'],'size':a['size'],'web_view_link':a['web_view_link'],'relative_path':a['relative_path'],'is_folder':0,'available':1}
  else:
   r=await asyncio.to_thread(self.bot.db.one,'SELECT * FROM drive_items WHERE guild_id=? AND file_id=? AND available=1',(self.guild_id,fid))
   if not r:return await i.response.send_message('That Drive item is no longer indexed.',ephemeral=True)
   r=dict(r)
  if r['is_folder']:
   return await i.response.send_message(f'📁 **{r["name"]}**\nBrowse this folder, open it in Google Drive, or package the entire folder as a ZIP.',view=DriveFolderActionView(self,r),ephemeral=True)
  s=await asyncio.to_thread(self.bot.db.guild,self.guild_id)
  if not s.get('downloads_enabled',1):return await i.response.send_message('Downloads are disabled by an administrator.',ephemeral=True)
  limit=i.guild.filesize_limit if i.guild else 10*1024*1024;size=int(r['size'] or 0)
  # Drive is the primary delivery path. Always give the user a Drive link first;
  # Discord upload is an optional convenience only when the indexed size fits.
  view=DriveDeliveryView(self.bot,self.guild_id,r,limit)
  size_text=fmt_bytes(size) if size else 'size unknown'
  if archive_hit:
   msg=f'🗜️ **Found inside:** `{a["member_path"]}`\n📦 **Full archive:** **{r["name"]}** • **{size_text}**\nThe result came from a parsed ZIP/RAR. Downloading returns the **complete original archive**, not only the internal member.'
  else:msg=f'☁️ **{r["name"]}** • **{size_text}**\nUse **Download from Drive** / **Open in Google Drive** below.'
  if size and size<=limit:msg+=f"\n📎 This file also fits Discord's **{fmt_bytes(limit)}** upload limit, so **Download to Discord** is available."
  elif size>limit:msg+=f"\n📦 Above Discord's **{fmt_bytes(limit)}** upload limit — Drive delivery is prioritized; no Discord upload will be attempted."
  else:msg+='\nℹ️ Drive delivery is prioritized because the indexed file size is unknown.'
  return await i.response.send_message(msg,view=view,ephemeral=True)

class DriveDeliveryView(discord.ui.View):
 def __init__(self,bot,guild_id,item,limit):
  super().__init__(timeout=600);self.bot=bot;self.guild_id=guild_id;self.item=dict(item);self.limit=int(limit)
  fid=self.item['file_id'];mime=self.item.get('mime_type') or '';web=self.item.get('web_view_link')
  # Google Workspace files cannot use the binary uc endpoint; their webViewLink
  # is the correct Drive-native path. Ordinary Drive files get a download URL.
  native=mime.startswith('application/vnd.google-apps.')
  if not native:
   self.add_item(discord.ui.Button(label='Download from Drive',emoji='☁️',url='https://drive.google.com/uc?export=download&id='+quote(fid,safe=''),row=0))
  if web:self.add_item(discord.ui.Button(label='Open in Google Drive',emoji='🌐',url=web,row=0))
  size=int(self.item.get('size') or 0)
  if size and size<=self.limit:self.add_item(DiscordDriveDownloadButton(row=1))

 async def interaction_check(self,i):
  state=await asyncio.to_thread(check_access,self.bot,i.guild,i.user)
  if not state.allowed:await i.response.send_message('Your 420Vault access is no longer active.',ephemeral=True);return False
  return True

 async def discord_download(self,i):
  r=self.item;size=int(r.get('size') or 0)
  if not size or size>self.limit:return await i.response.send_message('This item cannot be uploaded through Discord. Use the Drive button instead.',ephemeral=True)
  await i.response.defer(thinking=True);tmp=Path(tempfile.mkdtemp(prefix='420drive_'))
  try:
   p=await self.bot.google_drive.download(r['file_id'],tmp,r.get('mime_type') or '',r['name']);actual=await asyncio.to_thread(lambda:p.stat().st_size)
   if actual>self.limit:
    return await i.followup.send(f"⚠️ The downloaded/exported file is **{fmt_bytes(actual)}**, above Discord's **{fmt_bytes(self.limit)}** limit. Use the Drive link above instead.",ephemeral=True)
   await i.followup.send(content=f'📎 **{p.name}**',file=discord.File(p,filename=p.name),ephemeral=True)
  except Exception as e:
   # A Drive API 403/permission/export failure must never strand the user: the
   # original response already contains Drive-native link buttons.
   await i.followup.send(f'⚠️ Discord delivery was unavailable (`{str(e)[:220]}`). Use the **Drive link above** instead.',ephemeral=True)
  finally:await asyncio.to_thread(shutil.rmtree,tmp,True)

class DiscordDriveDownloadButton(discord.ui.Button):
 def __init__(self,row=1):super().__init__(label='Download to Discord',emoji='📎',style=discord.ButtonStyle.secondary,row=row)
 async def callback(self,i):await self.view.discord_download(i)

class DriveFolderActionView(discord.ui.View):
 def __init__(self,browser,row):
  super().__init__(timeout=600);self.browser=browser;self.row=dict(row)
  if self.row.get('web_view_link'):self.add_item(discord.ui.Button(label='Open in Google Drive',emoji='🌐',url=self.row['web_view_link'],row=1))
 async def interaction_check(self,i):return await self.browser.interaction_check(i)
 @discord.ui.button(label='Open Folder',emoji='📂',style=discord.ButtonStyle.primary)
 async def open_folder(self,i,b):
  v=self.browser;v.stack.append(v.parent) if v.mode=='browse' else v.stack.clear();v.mode='browse';v.parent=self.row['file_id'];v.page=1;await i.response.defer();await v.async_refresh();await i.edit_original_response(content=None,embed=v.embed(),view=v.rebuild())
 @discord.ui.button(label='Download Folder as ZIP',emoji='🗜️',style=discord.ButtonStyle.green)
 async def zip_folder(self,i,b):
  await i.response.defer(ephemeral=True,thinking=True);tmp=Path(tempfile.mkdtemp(prefix='420drivefolder_'))
  try:
   z,count=await self.browser.bot.google_drive.download_folder_zip(self.browser.guild_id,self.row['file_id'],self.row['name'],tmp);size=await asyncio.to_thread(lambda:z.stat().st_size);limit=i.guild.filesize_limit if i.guild else 10*1024*1024
   if size>limit:return await i.followup.send(f'ZIP created (**{fmt_bytes(size)}**, {count:,} items) but it is above Discord’s **{fmt_bytes(limit)}** upload limit. Download individual Drive files or use Drive-native access for large folders.',ephemeral=True)
   await i.followup.send(content=f'🗜️ **{self.row["name"]}.zip** • {count:,} item(s)',file=discord.File(z,filename=z.name),ephemeral=True)
  except Exception as e:await i.followup.send(f'Folder ZIP failed: `{type(e).__name__}: {str(e)[:300]}`',ephemeral=True)
  finally:await asyncio.to_thread(shutil.rmtree,tmp,True)
