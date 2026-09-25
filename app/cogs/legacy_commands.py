from __future__ import annotations
import asyncio, io, random
from datetime import datetime, timedelta, timezone
from pathlib import Path
import discord
from discord.ext import commands
from app.core.security import is_admin
from app.services.access import check_access
from app.services.indexer import VaultIndexer
from app.services.link_library import LinkLibrary
from app.views.paginator import fmt_bytes
from app.views.search_hub import UnifiedSearchView
from app.views.vault_browser import VaultSearchView
from app.views.drive_browser import DriveBrowserView
from app.views.setup import SetupView
from app.views.admin import AdminView
from app.views.subscriptions import SubscribeView
from app.views.license import LicenseView, DMLicenseView, license_embed
from app.views.tos import TosStartView,accepted,publish_tos
from app.views.manuals import ManualView
from app.views.remote_browser import RemoteBrowserView


class LegacyCommands(commands.Cog):
 """Compatibility text commands. Prefix is 420_. New slash/GUI commands remain available."""
 def __init__(self,bot): self.bot=bot; self.lockdown_mode=False
 async def cog_check(self,ctx):
  if not ctx.guild:return True
  if self.lockdown_mode and not check_access(self.bot,ctx.guild,ctx.author,require_admin=True).allowed:
   await ctx.send('🚨 420Vault is currently in lockdown.');return False
  # Administrators/Owner bypass onboarding so management commands never get trapped behind TOS.
  admin_state=check_access(self.bot,ctx.guild,ctx.author,require_admin=True)
  if admin_state.allowed:return True
  # Before Terms/access, the only text command intentionally exposed is 420_subscribe.
  # Terms verification itself is performed from the persistent #terms panel.
  if ctx.command and ctx.command.name in {'subscribe','help','user_manual'}:return True
  state=check_access(self.bot,ctx.guild,ctx.author)
  if state.allowed:return True
  await ctx.send('⛔ **You are not authorized to use this command.**\nChoose a subscription below to unlock paid commands.',view=SubscribeView(self.bot,ctx.guild.id,ctx.author.id));return False
 def admin(self,ctx): return bool(ctx.guild and is_admin(ctx,self.bot.db.guild(ctx.guild.id)))
 async def need_admin(self,ctx):
  if self.admin(ctx):return True
  await ctx.send('⛔ Administrator access is required.');return False
 async def licensed(self,ctx):
  return bool(ctx.guild and check_access(self.bot,ctx.guild,ctx.author).allowed)
 async def private_admin(self,ctx,content=None,embed=None):
  try: await ctx.author.send(content=content,embed=embed); return True
  except (discord.Forbidden,discord.HTTPException):
   await ctx.send('⚠️ I could not DM you. Enable DMs from server members and try again.'); return False
 async def safe_delete_invocation(self,ctx):
  try: await ctx.message.delete()
  except (discord.Forbidden,discord.HTTPException): pass

 @commands.command(name='help')
 async def help_cmd(self,ctx):
  user_cmds=['help','user_manual','server_search','status','Bot_status','version','search [query]','vault_search [query]','drive_search','subscribe','subscription','vault_search_type <ext> [limit] [page]','vault_search_size <operator> <size> [limit] [page]','vault_search_terms <terms>','vault_random','vault_stats','vault_list [path] [page]','download_vault <id>','sendlink <query> <#channel>']
  admin_cmds=['admin_manual','setup','admin','diagnostics','vault_path <folder>','reloadlinks','resolvelinks','showchannels','reindex_vault','admin_delete_vault_index','drive_config [folder URL or ID]','drive_sync','drive_status','lockdown','unlock','exportserver','addlicense [user] [days] [max_activations]','revokelicense <code>','showlicense <code>','listlicenses [status]','resetuserlicenses <user>','approvepayment <transaction_id>','resendlicense <user>']
  state=check_access(self.bot,ctx.guild,ctx.author) if ctx.guild else None
  restricted=bool(ctx.guild and not self.admin(ctx) and not (state and state.allowed))
  shown=['help','subscribe','user_manual'] if restricted else user_cmds
  e=discord.Embed(title='420VaultBot Commands',description='Prefix: `420_`\n'+('Your account is currently restricted. Subscribe/activate access to unlock paid commands.' if restricted else 'Your account can use the commands shown below.'))
  e.add_field(name='Available commands',value='\n'.join(f'`420_{x}`' for x in shown),inline=False)
  if self.admin(ctx):e.add_field(name='Administrator commands',value='\n'.join(f'`420_{x}`' for x in admin_cmds),inline=False)
  await ctx.send(embed=e)


 @commands.command(name='user_manual')
 async def user_manual(self,ctx):
  v=ManualView(ctx.author.id,False);await ctx.send(embed=v.embed(),view=v)

 @commands.command(name='admin_manual')
 async def admin_manual(self,ctx):
  if not await self.need_admin(ctx):return
  v=ManualView(ctx.author.id,True);await ctx.send(embed=v.embed(),view=v)


 @commands.command(name='tos')
 async def tos_cmd(self,ctx):
  if not ctx.guild:return
  await ctx.send(embed=discord.Embed(title='📜 420Vault Terms Verification',description='Click below to read the current Terms and complete the comprehension check.'),view=TosStartView(self.bot))

 @commands.command(name='setup')
 async def setup_gui(self,ctx):
  if not ctx.guild or not ctx.author.guild_permissions.administrator:return await ctx.send('Server Administrator permission is required.')
  st=self.bot.db.guild(ctx.guild.id); ids=self.bot.db.channels(ctx.guild.id,'search');e=discord.Embed(title='⚙️ 420Vault Setup',description='Configure multiple allowed search/delivery channels, the persistent license activation channel, logging, and access roles. No hard-coded IDs.')
  e.add_field(name='Allowed search channels',value=' '.join(f'<#{x}>' for x in ids) if ids else 'Not set (search allowed everywhere until configured)',inline=False);e.add_field(name='License activation channel',value=f'<#{st["license_channel_id"]}>' if st['license_channel_id'] else 'Not set');e.add_field(name='Admin role',value=f'<@&{st["admin_role_id"]}>' if st['admin_role_id'] else 'Discord Administrators')
  await ctx.send(embed=e,view=SetupView(self.bot,ctx.guild.id))
 @commands.command(name='admin')
 async def admin_gui(self,ctx):
  st=self.bot.db.guild(ctx.guild.id)
  if not is_admin(ctx,st):return await ctx.send('Administrator access is required.')
  v=AdminView(self.bot,ctx.guild.id);await ctx.send(embed=v.embed(),view=v)
 @commands.command(name='vault_path')
 async def vault_path(self,ctx,*,path:str):
  if not await self.need_admin(ctx):return
  p=Path(path.strip().strip('\"')).expanduser()
  if not await asyncio.to_thread(p.is_dir):return await ctx.send('That folder does not exist on the computer running the bot.')
  resolved=await asyncio.to_thread(p.resolve);await asyncio.to_thread(self.bot.db.set_guild,ctx.guild.id,vault_path=str(resolved));await ctx.send(f'✅ Vault path saved as `{resolved}`. Run `420_reindex_vault` next.')
 @commands.command(name='diagnostics')
 async def diagnostics(self,ctx):
  if not await self.need_admin(ctx):return
  st=self.bot.db.guild(ctx.guild.id);n=self.bot.db.one('SELECT COUNT(*) n FROM vault_files WHERE guild_id=?',(ctx.guild.id,))['n'];await ctx.send(f'🩺 Database: OK\nSearch channel: {f"<#{st["search_channel_id"]}>" if st["search_channel_id"] else "Not set"}\nLicense channel: {f"<#{st["license_channel_id"]}>" if st["license_channel_id"] else "Not set"}\nVault path: `{st["vault_path"] or "Not set"}`\nIndexed files: **{n:,}**\nLoaded links: **{len(self.bot.link_search.links):,}**\nHeartbeat: **{'ALIVE' if self.bot.heartbeat_watchdog.snapshot()['thread_alive'] else 'STOPPED'}** • {self.bot.heartbeat_watchdog.snapshot()['interval_seconds']}s • latency {self.bot.heartbeat_watchdog.snapshot()['latency_ms'] if self.bot.heartbeat_watchdog.snapshot()['latency_ms'] is not None else 'n/a'} ms\nKeep system awake: **{'ON' if self.bot.heartbeat_watchdog.snapshot()['prevent_sleep'] else 'OFF'}** (display may turn off)')
 @commands.command(name='search',aliases=['searchkit'])
 async def search_panel(self,ctx,*,query:str=''):
  s=self.bot.db.guild(ctx.guild.id);allowed=self.bot.db.channels(ctx.guild.id,'search')
  if allowed and ctx.channel.id not in allowed:return await ctx.send('Use 420Vault search in one of: '+', '.join(f'<#{x}>' for x in allowed))
  v=UnifiedSearchView(self.bot,ctx.author.id,s['results_per_page'],s['max_search_results'],query,ctx.guild.id)
  if query:await v.load()
  await ctx.send(content=v.native_content(),embeds=v.embeds(),view=v)
 @commands.command(name='vault_search')
 async def vault_search_panel(self,ctx,*,query:str=''):
  s=self.bot.db.guild(ctx.guild.id);allowed=self.bot.db.channels(ctx.guild.id,'search')
  if allowed and ctx.channel.id not in allowed:return await ctx.send('Use 420Vault search in one of: '+', '.join(f'<#{x}>' for x in allowed))
  v=VaultSearchView(self.bot,ctx.author.id,ctx.guild.id,s['results_per_page'],s['max_search_results'],query)
  await ctx.send(embed=v.embed(),view=v)

 @commands.command(name='server_search')
 async def server_search(self,ctx):
  if not ctx.guild:return
  v=RemoteBrowserView(self.bot,ctx.author.id,ctx.guild.id);await ctx.send(embed=v.embed(),view=v)

 @commands.command(name='drive_search')
 async def drive_search(self,ctx):
  s=self.bot.db.guild(ctx.guild.id);allowed=self.bot.db.channels(ctx.guild.id,'search')
  if allowed and ctx.channel.id not in allowed:return await ctx.send('Use 420Vault search in one of: '+', '.join(f'<#{x}>' for x in allowed))
  src=self.bot.db.one('SELECT * FROM drive_sources WHERE guild_id=? AND enabled=1',(ctx.guild.id,))
  if not src:return await ctx.send('☁️ Google Drive Search is not configured for this server. An admin can use `420_drive_config <Google Drive folder URL or ID>`.')
  v=DriveBrowserView(self.bot,ctx.author.id,ctx.guild.id,s['results_per_page'],s['max_search_results']);await v.async_refresh();v.rebuild();await ctx.send(embed=v.embed(),view=v)

 @commands.command(name='drive_config')
 async def drive_config(self,ctx,*,folder:str=''):
  if not await self.need_admin(ctx):return
  if not folder:
   from app.views.admin import AdminView
   v=AdminView(self.bot,ctx.guild.id,'drive');return await ctx.send(embed=v.embed(),view=v)
  try:m=await self.bot.google_drive.configure(ctx.guild.id,folder);await ctx.send(f'✅ Google Drive root configured: **{m["name"]}**. Open `420_admin` → **Google Drive** to sync and manage it.')
  except Exception as e:await ctx.send(f'❌ Google Drive configuration failed: `{str(e)[:500]}`')

 @commands.command(name='drive_sync')
 @commands.max_concurrency(1,per=commands.BucketType.guild,wait=False)
 async def drive_sync(self,ctx):
  if not await self.need_admin(ctx):return
  try:
   started=await self.bot.google_drive.start_sync(ctx.guild.id)
   if not started:return await ctx.send('🟡 A Google Drive metadata sync is already running. Use `420_drive_status` to watch it.')
   await ctx.send('🟡 Google Drive metadata sync started in the background. The bot remains responsive; use `420_drive_status` for progress.')
  except Exception as e:await ctx.send(f'❌ Google Drive sync failed to start: `{str(e)[:500]}`')

 @commands.command(name='drive_status')
 async def drive_status(self,ctx):
  if not await self.need_admin(ctx):return
  r=self.bot.db.one('SELECT * FROM drive_sources WHERE guild_id=?',(ctx.guild.id,))
  if not r:return await ctx.send('Google Drive is not configured.')
  await ctx.send(f'☁️ **Google Drive**: {r["root_name"]}\nStatus: **{r["last_status"] or "unknown"}**\nIndexed: **{r["item_count"]:,}**\nLast sync: **{r["last_sync"] or "Never"}**')

 @commands.command(name='sendlink')
 @commands.cooldown(2,30,commands.BucketType.user)
 async def sendlink(self,ctx,query:str,channel:discord.TextChannel):
  allowed=self.bot.db.channels(ctx.guild.id,'search')
  if allowed and (ctx.channel.id not in allowed or channel.id not in allowed):return await ctx.send('sendlink is restricted to configured 420Vault search/delivery channels.')
  r=await asyncio.to_thread(self.bot.link_search.search,query,1,250,250,ctx.guild.id)
  if not r.items:return await ctx.send('No matching links found.')
  await channel.send(random.choice(r.items));await ctx.send(f'✅ Sent a random match to {channel.mention}.')
 @commands.command(name='importlinks')
 async def importlinks(self,ctx,*,list_name:str='Imported Links'):
  if not await self.need_admin(ctx):return
  if not ctx.message.attachments:return await ctx.send('📥 Attach a `.txt` link list to the same message: `420_importlinks My List`')
  a=ctx.message.attachments[0]
  if a.size>25*1024*1024:return await ctx.send('❌ Link-list file is too large (25 MB import safety limit).')
  if not a.filename.lower().endswith(('.txt','.csv')):return await ctx.send('❌ Upload a `.txt` or `.csv` link list.')
  raw=(await a.read()).decode('utf-8','ignore');urls=[]
  for line in raw.splitlines():
   line=line.strip().strip('\"').strip("'")
   if line.startswith(('http://','https://')):urls.append(line.split(',')[0].strip())
  r=await asyncio.to_thread(LinkLibrary(self.bot.db).ingest,ctx.guild.id,list_name,urls,'import',None,f'Imported from {a.filename}')
  await ctx.send(f'✅ **{list_name}** imported + incrementally indexed.\nParsed: **{len(urls):,}** • New: **{r["added"]:,}** • Already indexed: **{r["existing"]:,}** • Invalid: **{r["invalid"]:,}**')

 @commands.command(name='reloadlinks')
 async def reloadlinks(self,ctx):
  if not await self.need_admin(ctx):return
  n=await asyncio.to_thread(self.bot.link_search.reload);await ctx.send(f'✅ Reloaded {n:,} unique links.')
 @commands.command(name='resolvelinks')
 async def resolvelinks(self,ctx):
  if not await self.need_admin(ctx):return
  await ctx.send('✅ v2 stores channel IDs from `420_setup`; name resolution is no longer required.')
 @commands.command(name='showchannels')
 async def showchannels(self,ctx):
  if not await self.need_admin(ctx):return
  s=self.bot.db.guild(ctx.guild.id);await ctx.send(f'Search: {f"<#{s["search_channel_id"]}>" if s["search_channel_id"] else "Not set"}\nLicense: {f"<#{s["license_channel_id"]}>" if s["license_channel_id"] else "Not set"}\nLogs: {f"<#{s["log_channel_id"]}>" if s["log_channel_id"] else "Not set"}')
 @commands.command(name='status',aliases=['Bot_status'])
 async def status(self,ctx):
  from app.version import VERSION
  await ctx.send(f'🟢 420VaultBot v{VERSION} operational • Links: {len(self.bot.link_search.links):,} • Lockdown: {"ON" if self.lockdown_mode else "OFF"}')
 @commands.command(name='version')
 async def version(self,ctx):
  from app.version import VERSION
  await ctx.send(f'420VaultBot v{VERSION}')

 async def send_files_page(self,ctx,r,title):
  e=discord.Embed(title=title,description=f'{r.total:,} result(s)')
  for x in r.items:e.add_field(name=f'ID {x["id"]} • {x["filename"]}',value=f'{fmt_bytes(x["file_size"])} • `{x["folder"] or "/"}`',inline=False)
  e.set_footer(text=f'Page {r.page}/{r.pages} • Use `420_vault_search` for GUI pagination.');await ctx.send(embed=e)
 @commands.command(name='vault_search_type')
 async def vault_search_type(self,ctx,extension:str,limit:int=5,page:int=1):
  r=await asyncio.to_thread(self.bot.search.search,'',page,max(1,min(limit,20)),extension,250,ctx.guild.id);await self.send_files_page(ctx,r,f'Vault Type: .{extension.lstrip(".")}')
 @commands.command(name='vault_search_size')
 async def vault_search_size(self,ctx,operator:str,value:str,limit:int=5,page:int=1):
  mult={'kb':1024,'mb':1024**2,'gb':1024**3};v=value.lower().strip();num=''.join(c for c in v if c.isdigit() or c=='.');unit=''.join(c for c in v if c.isalpha()) or 'b'
  try:size=int(float(num)*mult.get(unit,1))
  except:return await ctx.send('Use a size like `100MB`, `2GB`, or `500KB`.')
  op=operator if operator in ('>','>=','<','<=','=') else '=';rows=self.bot.db.all(f'SELECT id,filename,folder,extension,file_size,full_path FROM vault_files WHERE guild_id=? AND file_size {op} ? ORDER BY file_size DESC LIMIT ? OFFSET ?',(ctx.guild.id,size,max(1,min(limit,20)),(max(1,page)-1)*max(1,min(limit,20))))
  e=discord.Embed(title=f'Vault Size Search: {operator} {value}');
  for x in rows:e.add_field(name=f'ID {x["id"]} • {x["filename"]}',value=f'{fmt_bytes(x["file_size"])} • `{x["folder"] or "/"}`',inline=False)
  await ctx.send(embed=e)
 @commands.command(name='vault_search_terms')
 async def vault_search_terms(self,ctx,*,terms:str): await ctx.invoke(self.bot.get_command('vault_search'),query=terms)
 @commands.command(name='vault_random')
 async def vault_random(self,ctx):
  x=self.bot.search.random(ctx.guild.id);await ctx.send('Vault index is empty.' if not x else f'🎲 `ID {x["id"]}` **{x["filename"]}** • {fmt_bytes(x["file_size"])}')
 @commands.command(name='vault_stats')
 async def vault_stats(self,ctx):
  r=self.bot.db.one('SELECT COUNT(*) n,COALESCE(SUM(file_size),0) size,COUNT(DISTINCT extension) exts FROM vault_files WHERE guild_id=?',(ctx.guild.id,));await ctx.send(f'📊 Files: **{r["n"]:,}** • Size: **{fmt_bytes(r["size"])}** • Types: **{r["exts"]}**')
 @commands.command(name='vault_list')
 async def vault_list(self,ctx,path:str='',page:int=1):
  s=self.bot.db.guild(ctx.guild.id)
  if not s['vault_path']:return await ctx.send('Vault path is not configured. Use `420_vault_path <folder>`.')
  def _list():
   base=Path(s['vault_path']).resolve();target=(base/path).resolve()
   if base!=target and base not in target.parents:return base,target,None
   if not target.is_dir():return base,target,[]
   return base,target,sorted(target.iterdir(),key=lambda p:(not p.is_dir(),p.name.lower()))
  base,target,entries=await asyncio.to_thread(_list)
  if entries is None:return await ctx.send('Path must stay inside the Vault.')
  if entries==[] and not await asyncio.to_thread(target.is_dir):return await ctx.send('Folder not found.')
  per=10;start=(max(1,page)-1)*per;e=discord.Embed(title=f'📁 {path or "/"}')
  e.description='\n'.join(('📁 ' if p.is_dir() else '📄 ')+p.name for p in entries[start:start+per]) or 'Empty folder';e.set_footer(text=f'Page {page}');await ctx.send(embed=e)
 @commands.command(name='download_vault')
 async def download_vault(self,ctx,file_id:int):
  s=self.bot.db.guild(ctx.guild.id)
  if not s['downloads_enabled']:return await ctx.send('Downloads are disabled.')
  r=self.bot.db.one('SELECT * FROM vault_files WHERE guild_id=? AND id=?',(ctx.guild.id,file_id));
  if not r:return await ctx.send('File ID not found.')
  p=Path(r['full_path']);limit=ctx.guild.filesize_limit
  if not await asyncio.to_thread(p.is_file):return await ctx.send('Indexed file is missing; reindex the Vault.')
  size=await asyncio.to_thread(lambda:p.stat().st_size)
  if size>limit:return await ctx.send(f'File is {fmt_bytes(size)}, above this server upload limit ({fmt_bytes(limit)}).')
  await ctx.send(file=discord.File(p))
 @commands.command(name='reindex_vault')
 async def reindex_vault(self,ctx):
  if not await self.need_admin(ctx):return
  s=self.bot.db.guild(ctx.guild.id)
  if not s['vault_path']:return await ctx.send('Set the Vault path with `420_vault_path <folder>`.')
  m=await ctx.send('⚙️ Reindexing…');indexed,removed=await asyncio.to_thread(VaultIndexer(self.bot.db).rebuild,s['vault_path'],ctx.guild.id);await m.edit(content=f'✅ {indexed:,} indexed; {removed:,} stale removed.')
 @commands.command(name='admin_delete_vault_index')
 async def delete_index(self,ctx):
  if not await self.need_admin(ctx):return
  await ctx.send('Type `CONFIRM DELETE INDEX` within 15 seconds.')
  try:await self.bot.wait_for('message',timeout=15,check=lambda m:m.author==ctx.author and m.channel==ctx.channel and m.content=='CONFIRM DELETE INDEX')
  except asyncio.TimeoutError:return await ctx.send('Cancelled.')
  self.bot.db.execute('DELETE FROM vault_files WHERE guild_id=?',(ctx.guild.id,));self.bot.db.execute('DELETE FROM vault_folders WHERE guild_id=?',(ctx.guild.id,));self.bot.db.execute('DELETE FROM vault_fts WHERE guild_id=?',(ctx.guild.id,));await ctx.send('✅ Vault index cleared. Files on disk were not deleted.')
 @commands.command(name='lockdown')
 async def lockdown(self,ctx):
  if not await self.need_admin(ctx):return
  self.lockdown_mode=True;await ctx.send('🚨 LOCKDOWN ENABLED — public text commands disabled.')
 @commands.command(name='unlock')
 async def unlock(self,ctx):
  if not self.admin(ctx):return await ctx.send('Administrator access is required.')
  self.lockdown_mode=False;await ctx.send('✅ Lockdown disabled.')
 @commands.command(name='exportserver')
 async def exportserver(self,ctx):
  if not await self.need_admin(ctx):return
  g=ctx.guild;lines=[f'SERVER EXPORT\nName: {g.name}\nID: {g.id}\nMembers: {g.member_count}\n','ROLES:']+[f'- {r.name} (ID: {r.id})' for r in reversed(g.roles)]+['','CHANNELS:']+[f'- {c.name} ({type(c).__name__} | ID: {c.id})' for c in g.channels]
  data='\n'.join(lines).encode();await ctx.send(file=discord.File(io.BytesIO(data),filename=f'{g.name}_server_export.txt'))

 @commands.command(name='addlicense')
 async def addlicense(self,ctx,user:discord.Member|None=None,days_valid:int|None=None,max_activations:int=1):
  if not await self.need_admin(ctx):return
  if not user:return await ctx.send('Usage: `420_addlicense @user <days>` — use `0` for an intentional lifetime admin grant.')
  days=0 if days_valid is None else max(0,days_valid)
  eid,code,exp=self.bot.subscriptions.admin_grant(ctx.guild.id,user.id,days,ctx.author.id)
  if max_activations!=1:self.bot.db.execute('UPDATE licenses SET max_activations=? WHERE code=?',(max(1,max_activations),code))
  self.bot.db.audit(ctx.guild.id,ctx.author.id,'admin_entitlement_grant',f'user={user.id} days={days or "lifetime"} entitlement={eid}')
  e=discord.Embed(title='✨ 420Vault Admin Grant',description='This is an explicit administrator-granted entitlement. It does not pretend a payment occurred.',color=discord.Color.green());e.add_field(name='Code',value=f'`{code}`',inline=False);e.add_field(name='Bound to',value=user.mention);e.add_field(name='Access',value='Lifetime' if not exp else f'{days} days');e.add_field(name='Expires',value=exp.isoformat() if exp else 'Never')
  await self.private_admin(ctx,embed=e);ok=await self.bot.deliver_license(ctx.guild.id,user.id,code,None,exp);await self.bot.ensure_license_panel(ctx.guild.id,force=True)
  await ctx.send('✅ Admin grant created and activation DM sent.' if ok else '⚠️ Admin grant created, but Discord rejected the user DM.')
 @commands.command(name='subscribe')
 async def subscribe(self,ctx):
  self.bot.db.seed_plans(ctx.guild.id);e=discord.Embed(title='🌿 420Vault Subscriptions',description='Choose a plan below. Automated access is granted only after a verified provider webhook. Cash App payments require administrator approval.',color=discord.Color.green());await ctx.send(embed=e,view=SubscribeView(self.bot,ctx.guild.id,ctx.author.id))
 @commands.command(name='subscription')
 async def subscription(self,ctx):
  s=self.bot.subscriptions.active_for(ctx.guild.id,ctx.author.id)
  if s:return await ctx.send(f'📅 **{s["plan_name"]}** • status: **{s["status"]}** • expires: **{s["expires_at"] or "Never"}** • auto-renew: **{"on" if s["auto_renew"] else "off"}')
  ent=self.bot.subscriptions.entitlement_for(ctx.guild.id,ctx.author.id)
  if ent:return await ctx.send(f'🎟️ **Administrator Access Grant** • status: **{ent["status"]}** • expires: **{ent["expires_at"] or "Never"}** • payment subscription: **not required (admin-authorized)**')
  await ctx.send('You do not have an active subscription or administrator access grant.')
 @commands.command(name='approvepayment')
 async def approvepayment(self,ctx,transaction_id:int):
  if not await self.need_admin(ctx):return
  t=self.bot.db.one("SELECT * FROM transactions WHERE id=? AND guild_id=? AND provider='cashapp'",(transaction_id,ctx.guild.id))
  if not t:return await ctx.send('Cash App transaction not found.')
  if t['status']=='paid':return await ctx.send('That payment is already approved.')
  try:sid,c,p,exp,created=self.bot.subscriptions.approve_manual_transaction(transaction_id)
  except ValueError as ex:return await ctx.send(str(ex))
  if created:await self.bot.deliver_license(ctx.guild.id,t['user_id'],c,p,exp)
  self.bot.db.audit(ctx.guild.id,ctx.author.id,'manual_payment_approved',f'transaction={transaction_id} created={created}');await ctx.send('✅ Payment approval committed atomically; duplicate approval is idempotent.')
 @commands.command(name='resendlicense')
 async def resendlicense(self,ctx,user:discord.Member):
  if not await self.need_admin(ctx):return
  r=self.bot.db.one("SELECT * FROM licenses WHERE guild_id=? AND assigned_user_id=? AND status='active' ORDER BY created_at DESC LIMIT 1",(ctx.guild.id,user.id))
  if not r:return await ctx.send('No active assigned license found.')
  p=self.bot.db.one("SELECT p.* FROM subscriptions s JOIN subscription_plans p ON p.id=s.plan_id WHERE s.license_code=?",(r['code'],));ok=await self.bot.deliver_license(ctx.guild.id,user.id,r['code'],p,r['expires_at']);await ctx.send('✅ License DM sent.' if ok else '⚠️ Discord rejected the DM. Ask the user to enable server DMs.')
 @commands.command(name='revokelicense')
 async def revokelicense(self,ctx,code:str):
  if not await self.need_admin(ctx):return
  await self.safe_delete_invocation(ctx)
  self.bot.db.execute("UPDATE licenses SET status='revoked' WHERE code=? AND guild_id=?",(code.upper(),ctx.guild.id));await ctx.send('✅ License revoked.')
 @commands.command(name='showlicense')
 async def showlicense(self,ctx,code:str):
  if not await self.need_admin(ctx):return
  await self.safe_delete_invocation(ctx)
  r=self.bot.db.one('SELECT * FROM licenses WHERE code=? AND guild_id=?',(code.upper(),ctx.guild.id))
  await self.private_admin(ctx,content='License not found.' if not r else f'`{r["code"]}` • status={r["status"]} • user={r["user_id"] or "unbound"} • activations={r["activations"]}/{r["max_activations"]} • expires={r["expires_at"] or "never"}')
 @commands.command(name='listlicenses')
 async def listlicenses(self,ctx,status_filter:str|None=None):
  if not await self.need_admin(ctx):return
  rows=self.bot.db.all('SELECT * FROM licenses WHERE guild_id=?'+(' AND status=?' if status_filter else '')+' ORDER BY created_at DESC LIMIT 50',((ctx.guild.id,status_filter) if status_filter else (ctx.guild.id,)))
  await self.private_admin(ctx,content='\n'.join(f'`{r["code"]}` • {r["status"]} • user {r["user_id"] or "unbound"}' for r in rows) or 'No licenses.')
 @commands.command(name='resetuserlicenses')
 async def resetuserlicenses(self,ctx,user:discord.Member):
  if not await self.need_admin(ctx):return
  self.bot.db.execute('UPDATE licenses SET user_id=NULL,activations=0 WHERE guild_id=? AND user_id=?',(ctx.guild.id,user.id));await ctx.send(f'✅ Reset license bindings for {user.mention}.')

 async def cog_command_error(self,ctx,error):
  if isinstance(error,commands.MissingRequiredArgument):return await ctx.send(f'Missing input. Usage: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`')
  if isinstance(error,commands.BadArgument):return await ctx.send(f'Invalid input: `{error}`')
  if isinstance(error,commands.CheckFailure):return
  await ctx.send(f'❌ Command failed: `{type(error).__name__}: {error}`')

async def setup(bot):await bot.add_cog(LegacyCommands(bot))
