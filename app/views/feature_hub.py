from __future__ import annotations
import asyncio
import discord
from app.services.link_library import normalize_url
from app.views.paginator import fmt_bytes

class SiteSearchModal(discord.ui.Modal,title='Search Links by Website'):
 site=discord.ui.TextInput(label='Website / domain',placeholder='example.com',max_length=200)
 query=discord.ui.TextInput(label='Optional keywords',placeholder='serum, omnisphere, drum kit...',required=False,max_length=100)
 def __init__(self,view):super().__init__();self.v=view
 async def on_submit(self,i):
  clean=str(self.site).strip().lower().replace('https://','').replace('http://','').split('/')[0].lstrip('www.')
  if not clean or '.' not in clean:return await i.response.send_message('Enter a domain such as `example.com`.',ephemeral=True)
  from app.views.search_hub import UnifiedSearchView
  q=('site:'+clean+' '+str(self.query).strip()).strip();s=self.v.bot.db.guild(self.v.gid)
  v=UnifiedSearchView(self.v.bot,i.user.id,s['results_per_page'],s['max_search_results'],q,self.v.gid);await v.load()
  await i.response.send_message(content=v.native_content(),embeds=v.embeds(),view=v,ephemeral=True)

class FeatureHubView(discord.ui.View):
 def __init__(self,bot,owner_id,gid):super().__init__(timeout=900);self.bot=bot;self.owner_id=owner_id;self.gid=gid
 async def interaction_check(self,i):
  if i.user.id!=self.owner_id:await i.response.send_message('Open your own 420Vault feature panel.',ephemeral=True);return False
  return True
 def _stats(self):
  v=self.bot.db.one('SELECT COUNT(*) n,COALESCE(SUM(file_size),0) size,COUNT(DISTINCT extension) types FROM vault_files WHERE guild_id=?',(self.gid,)) or {'n':0,'size':0,'types':0}
  d=self.bot.db.one('SELECT COUNT(*) n,COALESCE(SUM(size),0) size FROM drive_items WHERE guild_id=? AND available=1 AND is_folder=0',(self.gid,)) or {'n':0,'size':0}
  m=self.bot.db.one('SELECT COUNT(*) n FROM links WHERE guild_id=?',(self.gid,)) or {'n':0}
  urls={normalize_url(u) for u in self.bot.link_search.links}
  try:
   for r in self.bot.db.all('SELECT normalized_url FROM links WHERE guild_id=?',(self.gid,)):urls.add(r['normalized_url'])
  except Exception:pass
  return v,d,m,len(urls)
 async def embed(self):
  v,d,m,total=await asyncio.to_thread(self._stats)
  e=discord.Embed(title='🌿 420VaultBot Feature Center',description='One GUI for library totals, search entry points, and the major user-facing capabilities.',color=discord.Color.dark_green())
  e.add_field(name='💾 Physical Vault',value=f'**{v["n"]:,} files**\n**{fmt_bytes(v["size"])}** indexed\n{v["types"]} file types',inline=True)
  e.add_field(name='☁️ Google Drive',value=f'**{d["n"]:,} files**\n**{fmt_bytes(d["size"])}** indexed',inline=True)
  e.add_field(name='🔗 Link Library',value=f'**{total:,} unique links**\n{m["n"]:,} managed DB links',inline=True)
  e.add_field(name='🔎 Search & Browse',value='Link browser • **Search by Site** • Physical Vault • Google Drive • Remote Server manifests • pagination • link preview cards',inline=False)
  e.add_field(name='🎧 Audio',value='WAV/MP3 auditioning before original download. Presets/projects remain normal files.',inline=False)
  e.add_field(name='🔐 Platform',value='Terms verification • subscriptions • signed licenses • Beta Tester/admin access • payment/ticket workflows • scraper/indexing • manuals • diagnostics',inline=False)
  e.set_footer(text='Use the buttons below — the stats/site tools are GUI actions, not separate commands.')
  return e
 @discord.ui.button(label='Search Links',emoji='🔎',style=discord.ButtonStyle.primary,row=0)
 async def links(self,i,b):
  from app.views.search_hub import UnifiedSearchView
  s=self.bot.db.guild(self.gid);v=UnifiedSearchView(self.bot,i.user.id,s['results_per_page'],s['max_search_results'],'',self.gid)
  await i.response.send_message(embeds=v.embeds(),view=v,ephemeral=True)
 @discord.ui.button(label='Search by Site',emoji='🌐',style=discord.ButtonStyle.success,row=0)
 async def site(self,i,b):await i.response.send_modal(SiteSearchModal(self))
 @discord.ui.button(label='Vault Browser',emoji='💾',style=discord.ButtonStyle.secondary,row=0)
 async def vault(self,i,b):
  from app.views.vault_browser import VaultSearchView
  s=self.bot.db.guild(self.gid);v=VaultSearchView(self.bot,i.user.id,self.gid,s['results_per_page'],s['max_search_results'],'')
  await i.response.send_message(embed=v.embed(),view=v,ephemeral=True)
 @discord.ui.button(label='Drive Browser',emoji='☁️',style=discord.ButtonStyle.secondary,row=1)
 async def drive(self,i,b):
  from app.views.drive_browser import DriveBrowserView
  src=self.bot.db.one('SELECT 1 FROM drive_sources WHERE guild_id=? AND enabled=1',(self.gid,))
  if not src:return await i.response.send_message('Google Drive is not configured for this server.',ephemeral=True)
  s=self.bot.db.guild(self.gid);v=DriveBrowserView(self.bot,i.user.id,self.gid,s['results_per_page'],s['max_search_results']);await v.async_refresh();v.rebuild();await i.response.send_message(embed=v.embed(),view=v,ephemeral=True)
 @discord.ui.button(label='Remote Browser',emoji='🖥️',style=discord.ButtonStyle.secondary,row=1)
 async def remote(self,i,b):
  from app.views.remote_browser import RemoteBrowserView
  v=RemoteBrowserView(self.bot,i.user.id,self.gid);await i.response.send_message(embed=v.embed(),view=v,ephemeral=True)
 @discord.ui.button(label='Refresh Stats',emoji='🔄',style=discord.ButtonStyle.secondary,row=1)
 async def refresh(self,i,b):await i.response.edit_message(embed=await self.embed(),view=self)
