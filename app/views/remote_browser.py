from __future__ import annotations
import discord
from app.views.paginator import fmt_bytes
class RemoteSearchModal(discord.ui.Modal,title='Search Remote File Servers'):
 query=discord.ui.TextInput(label='Search',placeholder='serum, drumkit, wav...',max_length=100)
 def __init__(self,v):super().__init__();self.v=v
 async def on_submit(self,i):self.v.query=str(self.query).strip();self.v.page=0;await i.response.edit_message(embed=self.v.embed(),view=self.v);self.v.build()
class RemoteSelect(discord.ui.Select):
 def __init__(self,v,rows):
  self.v=v;super().__init__(placeholder='Choose remote file…',options=[discord.SelectOption(label=r['name'][:100],description=(r['source_name']+' • '+fmt_bytes(r['size']))[:100],value=str(r['id'])) for r in rows] or [discord.SelectOption(label='No results',value='none')],disabled=not rows,row=1)
 async def callback(self,i):
  if self.values[0]=='none':return
  r=self.v.bot.db.one('SELECT * FROM remote_items WHERE guild_id=? AND id=?',(self.v.gid,int(self.values[0])))
  if not r or not r['available']:return await i.response.send_message('That remote item is currently unavailable.',ephemeral=True)
  e=discord.Embed(title='🖥️ '+r['name'],description=f'`{r["path"]}`\nSize: **{fmt_bytes(r["size"])}**');view=discord.ui.View(timeout=300);view.add_item(discord.ui.Button(label='Download from Server',emoji='⬇️',url=r['download_url']))
  if r['preview_url']:view.add_item(discord.ui.Button(label='Preview',emoji='🔊',url=r['preview_url']))
  await i.response.send_message(embed=e,view=view,ephemeral=True)
class RemoteBrowserView(discord.ui.View):
 def __init__(self,bot,owner,gid):super().__init__(timeout=600);self.bot=bot;self.owner=owner;self.gid=gid;self.query='';self.page=0;self.rows=[];self.build()
 def load(self):
  q='%'+self.query+'%';return self.bot.db.all('SELECT i.*,s.name source_name FROM remote_items i JOIN remote_sources s ON s.id=i.source_id WHERE i.guild_id=? AND i.available=1 AND (?="%%" OR i.name LIKE ? OR i.path LIKE ?) ORDER BY i.name LIMIT 25 OFFSET ?',(self.gid,q,q,q,self.page*25))
 def build(self):
  self.rows=self.load()
  for c in list(self.children):
   if isinstance(c,RemoteSelect):self.remove_item(c)
  self.add_item(RemoteSelect(self,self.rows))
 def embed(self):
  self.build();e=discord.Embed(title='🖥️ 420Vault — Remote File Servers',description=f'**Search:** {self.query or "Browse latest indexed items"}\nSelect a file for server-hosted delivery.');e.set_footer(text=f'Page {self.page+1} • v5.5 remote server index');return e
 async def interaction_check(self,i):
  if i.user.id!=self.owner:await i.response.send_message('This browser belongs to another user.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Search',emoji='🔎',style=discord.ButtonStyle.primary,row=0)
 async def search(self,i,b):await i.response.send_modal(RemoteSearchModal(self))
 @discord.ui.button(label='Previous',style=discord.ButtonStyle.secondary,row=0)
 async def prev(self,i,b):self.page=max(0,self.page-1);await i.response.edit_message(embed=self.embed(),view=self)
 @discord.ui.button(label='Next',style=discord.ButtonStyle.secondary,row=0)
 async def next(self,i,b):self.page+=1;await i.response.edit_message(embed=self.embed(),view=self)
