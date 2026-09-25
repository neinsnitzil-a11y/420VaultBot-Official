from __future__ import annotations
import os, asyncio, tempfile
from pathlib import Path
import discord
from app.services.indexer import VaultIndexer
from app.services.link_library import LinkLibrary, UniversalScraper
from app.services.remote_servers import RemoteServers
from app.views.paginator import fmt_bytes
from app.views.setup import SetupView
from app.views.tos import AccessRoleSetup,TosChannelSetup,publish_tos,TOS_VERSION,role_by_setting


_VAULT_TASKS={}
_VAULT_PROGRESS={}

def _vault_running(gid):
 t=_VAULT_TASKS.get(gid);return bool(t and not t.done())

def _start_vault_scan(bot,gid,path,full=False,user_id=None):
 if _vault_running(gid):return False
 loop=asyncio.get_running_loop();_VAULT_PROGRESS[gid]={'status':'starting','processed':0,'folders':0,'started':loop.time(),'current':path}
 def progress(data):_VAULT_PROGRESS[gid].update(data)
 async def runner():
  try:
   r=await asyncio.to_thread(VaultIndexer(bot.db).scan,gid,path,full,progress)
   if user_id:await asyncio.to_thread(bot.db.audit,gid,user_id,'vault_full_reindex' if full else 'vault_scan',f'processed {r.get("processed",0)} files')
  except Exception as e:_VAULT_PROGRESS[gid].update(status='failed',error=f'{type(e).__name__}: {e}')
  finally:_VAULT_TASKS.pop(gid,None)
 _VAULT_TASKS[gid]=asyncio.create_task(runner(),name=f'vault-scan-{gid}')
 return True

SECTIONS=[('overview','Overview','🏠'),('vault','Vault Storage','💾'),('drive','Google Drive','☁️'),('search','Search & Delivery','🔎'),('links','Link Library & Scraper','🔗'),('remote','Remote File Servers','🖥️'),('channels','Channels','📺'),('roles','Access Roles','👥'),('tos','Terms & Verification','📜'),('licensing','Licensing','🔑'),('subscriptions','Subscriptions','📅'),('payments','Payments','💳'),('transactions','Transactions','🧾'),('security','Security','🛡️'),('logs','Logs','📜'),('diagnostics','Diagnostics','🩺')]

def admin_ok(i,gid):
 from app.core.security import is_admin
 return is_admin(i,i.client.db.guild(gid))

class VaultModal(discord.ui.Modal,title='Vault Storage Configuration'):
 path=discord.ui.TextInput(label='Vault root path',placeholder=r'E:\\420Vault or F:\\MusicVault',max_length=400)
 def __init__(self,bot,gid):super().__init__();self.bot=bot;self.gid=gid;self.path.default=bot.db.guild(gid).get('vault_path') or ''
 async def on_submit(self,i):
  # Removable/network storage checks can block Windows. Acknowledge Discord first.
  await i.response.defer(ephemeral=True,thinking=True)
  raw=str(self.path).strip().strip('"')
  p=Path(raw).expanduser()
  ok=await asyncio.to_thread(p.is_dir)
  if not ok:return await i.followup.send(f'❌ **Vault Missing / Path Invalid**\n`{p}`\nExisting SQLite index was preserved.',ephemeral=True)
  p=await asyncio.to_thread(p.resolve)
  await asyncio.to_thread(self.bot.db.set_guild,self.gid,vault_path=str(p))
  started=_start_vault_scan(self.bot,self.gid,str(p),False,i.user.id)
  msg=f'✅ **Vault path saved**\n`{p}`\n\n' + ('🟡 Initial index started in the background. The bot will stay responsive; use **Stats** to check progress.' if started else '🟡 A Vault scan is already running.')
  await i.followup.send(msg,ephemeral=True)



class DriveRootModal(discord.ui.Modal,title='Google Drive Configuration'):
 root=discord.ui.TextInput(label='Drive root folder URL or ID',placeholder='https://drive.google.com/drive/folders/...',max_length=500)
 def __init__(self,bot,gid):
  super().__init__();self.bot=bot;self.gid=gid
  row=bot.db.one('SELECT root_file_id FROM drive_sources WHERE guild_id=?',(gid,))
  if row:self.root.default=row['root_file_id']
 async def on_submit(self,i):
  try:
   rid=await asyncio.to_thread(self.bot.google_drive.save_root,self.gid,str(self.root.value).strip())
   await asyncio.to_thread(self.bot.db.audit,self.gid,i.user.id,'drive_root_saved',f'saved Google Drive root {rid}')
   await i.response.send_message(f'✅ **Drive folder saved**\nFolder ID: `{rid}`\n\nOAuth does **not** need to be configured yet. Add credentials when ready, then press **Test Connection**.',ephemeral=True)
  except Exception as e:
   await i.response.send_message(f'❌ Could not save Drive folder: `{str(e)[:700]}`',ephemeral=True)

class DriveOAuthModal(discord.ui.Modal,title='Google Drive OAuth Credentials'):
 client_id=discord.ui.TextInput(label='Google OAuth Client ID',placeholder='...apps.googleusercontent.com',max_length=500)
 client_secret=discord.ui.TextInput(label='Google OAuth Client Secret',placeholder='Stored locally and never displayed back',max_length=500)
 refresh_token=discord.ui.TextInput(label='Google OAuth Refresh Token',placeholder='Offline-access refresh token',style=discord.TextStyle.paragraph,max_length=2000)
 def __init__(self,bot,gid):super().__init__();self.bot=bot;self.gid=gid
 async def on_submit(self,i):
  try:
   self.bot.google_drive.save_credentials(str(self.client_id),str(self.client_secret),str(self.refresh_token))
   self.bot.db.audit(self.gid,i.user.id,'drive_oauth_saved','saved Google Drive OAuth credentials locally')
   await i.response.send_message('✅ **Google OAuth credentials saved locally.**\nThey will not be displayed back in Discord. Now press **Test Connection**.',ephemeral=True)
  except Exception as e: await i.response.send_message(f'❌ Could not save OAuth credentials: `{str(e)[:700]}`',ephemeral=True)

class ScrapeModal(discord.ui.Modal,title='Universal Web Scraper'):
 url=discord.ui.TextInput(label='Target URL',placeholder='https://example.com',max_length=500)
 pages=discord.ui.TextInput(label='Maximum pages (1-20000)',default='2000',max_length=5)
 concurrency=discord.ui.TextInput(label='Concurrent pages (1-12)',default='6',max_length=2)
 def __init__(self,bot,gid):super().__init__();self.bot=bot;self.gid=gid
 async def on_submit(self,i):
  try: pages=max(1,min(int(self.pages.value),20000));conc=max(1,min(int(self.concurrency.value),12))
  except ValueError:return await i.response.send_message('❌ Page/concurrency values must be numbers.',ephemeral=True)
  target=str(self.url.value).strip();await i.response.defer(ephemeral=True,thinking=True)
  await i.edit_original_response(embed=discord.Embed(title='🌐 420Vault Live Web Scraper',description=f'Initializing live crawler…\n**Target:** {target[:300]}\n\nThe dashboard will update as links are discovered.'))
  jid=await asyncio.to_thread(self.bot.db.execute,'INSERT INTO scrape_jobs(guild_id,user_id,target_url,status) VALUES(?,?,?,?)',(self.gid,i.user.id,target,'running'))
  loop=asyncio.get_running_loop();last_update=0.0
  async def prog(pg,ln,er,q,current,recent):
   nonlocal last_update
   await asyncio.to_thread(self.bot.db.execute,'UPDATE scrape_jobs SET pages_crawled=?,links_found=?,errors=? WHERE id=?',(pg,ln,er,jid))
   now=loop.time()
   if now-last_update<1.0:return
   last_update=now
   stream='\n'.join('`'+x[:150]+'`' for x in recent[-8:]) or '_Waiting for links…_'
   e=discord.Embed(title='🌐 420Vault Live Web Scraper',description=f'**Status:** 🟢 SCRAPING\n**Target:** {target[:300]}\n\n**Pages scanned:** {pg:,}\n**Unique links:** {ln:,}\n**Errors:** {er:,}\n**Queue:** {q:,}\n\n**Current page**\n`{current[:250]}`',color=discord.Color.green());e.add_field(name='LIVE LINK STREAM',value=stream[:1024],inline=False);e.set_footer(text='v5.5 • dashboard refreshes about once per second')
   try:await i.edit_original_response(embed=e)
   except discord.HTTPException:pass
  try:
   urls,st=await UniversalScraper(pages,conc).scrape(target,prog)
   out=Path(tempfile.gettempdir())/f'420vault_scrape_{self.gid}_{jid}.txt';out.write_text('\n'.join(urls)+'\n',encoding='utf-8')
   part=await asyncio.to_thread(LinkLibrary(self.bot.db).save_scrape_part,self.gid,urls,target)
   await asyncio.to_thread(self.bot.db.execute,"UPDATE scrape_jobs SET status='complete',pages_crawled=?,links_found=?,errors=?,output_path=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",(st['pages'],st['links'],st['errors'],part['path'],jid))
   await i.followup.send(embed=discord.Embed(title='✅ Scrape Complete',description=f'**Target:** {target}\n**Pages:** {st["pages"]:,}\n**Unique links:** {st["links"]:,}\n**Errors:** {st["errors"]:,}\n\nAutomatically saved + indexed as **links_part_{part["part"]}.txt**\nNew indexed URLs: **{part["added"]:,}** • Existing/deduplicated: **{part["existing"]:,}**'),view=ScrapeResultView(self.bot,self.gid,jid,urls,target),ephemeral=True)
  except Exception as e:
   await asyncio.to_thread(self.bot.db.execute,"UPDATE scrape_jobs SET status='failed',last_error=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",(str(e)[:1000],jid));await i.followup.send(f'❌ Scrape failed: `{type(e).__name__}: {e}`',ephemeral=True)

class NewListModal(discord.ui.Modal,title='Create Link List'):
 name=discord.ui.TextInput(label='List name',max_length=80);description=discord.ui.TextInput(label='Description',required=False,style=discord.TextStyle.paragraph,max_length=500)
 def __init__(self,view):super().__init__();self.v=view
 async def on_submit(self,i):
  r=LinkLibrary(self.v.bot.db).ingest(self.v.gid,str(self.name.value),self.v.urls,'scrape',self.v.target,str(self.description.value));await i.response.send_message(f'✅ **{self.name.value}** created and indexed.\nNew: **{r["added"]:,}** • Existing: **{r["existing"]:,}** • Invalid: **{r["invalid"]:,}**',ephemeral=True)

class ExistingListSelect(discord.ui.Select):
 def __init__(self,v,rows):super().__init__(placeholder='Choose existing link list…',options=[discord.SelectOption(label=r['name'][:100],value=str(r['id']),description=f'{r["link_count"]:,} links') for r in rows[:25]]);self.v=v
 async def callback(self,i):
  lid=int(self.values[0]);row=self.v.bot.db.one('SELECT name FROM link_lists WHERE id=? AND guild_id=?',(lid,self.v.gid));
  if not row:return await i.response.send_message('List no longer exists.',ephemeral=True)
  r=LinkLibrary(self.v.bot.db).ingest(self.v.gid,row['name'],self.v.urls,'scrape',self.v.target);await i.response.send_message(f'✅ Merged into **{row["name"]}** and incrementally indexed.\nNew: **{r["added"]:,}** • Already indexed: **{r["existing"]:,}**',ephemeral=True)

class ExistingListView(discord.ui.View):
 def __init__(self,parent,rows):super().__init__(timeout=300);self.add_item(ExistingListSelect(parent,rows))

class ScrapeResultView(discord.ui.View):
 def __init__(self,bot,gid,jid,urls,target):super().__init__(timeout=1800);self.bot=bot;self.gid=gid;self.jid=jid;self.urls=urls;self.target=target
 @discord.ui.button(label='Create New List',emoji='✨',style=discord.ButtonStyle.success)
 async def new(self,i,b):await i.response.send_modal(NewListModal(self))
 @discord.ui.button(label='Add to Existing List',emoji='➕',style=discord.ButtonStyle.primary)
 async def existing(self,i,b):
  rows=LinkLibrary(self.bot.db).lists(self.gid)
  if not rows:return await i.response.send_message('No managed lists yet. Use **Create New List** first.',ephemeral=True)
  await i.response.send_message('Choose the destination list:',view=ExistingListView(self,rows),ephemeral=True)
 @discord.ui.button(label='Download TXT',emoji='📄',style=discord.ButtonStyle.secondary)
 async def download(self,i,b):
  p=self.bot.db.one('SELECT output_path FROM scrape_jobs WHERE id=? AND guild_id=?',(self.jid,self.gid));path=Path(p['output_path']) if p and p['output_path'] else None
  if not path or not path.is_file():return await i.response.send_message('Output file is no longer available.',ephemeral=True)
  await i.response.send_message(file=discord.File(path,filename=f'scrape_{self.jid}.txt'),ephemeral=True)
 @discord.ui.button(label='Preview',emoji='🔎',style=discord.ButtonStyle.secondary)
 async def preview(self,i,b):await i.response.send_message('\n'.join(f'`{u[:180]}`' for u in self.urls[:15]) or 'No links found.',ephemeral=True)

class SearchSettingsModal(discord.ui.Modal,title='Search & Delivery Settings'):
 per=discord.ui.TextInput(label='Results per page (1-10)',default='5');maximum=discord.ui.TextInput(label='Maximum search results (10-5000)',default='250')
 def __init__(self,bot,gid):
  super().__init__();self.bot=bot;self.gid=gid;s=bot.db.guild(gid);self.per.default=str(s['results_per_page']);self.maximum.default=str(s['max_search_results'])
 async def on_submit(self,i):
  try:p=max(1,min(10,int(str(self.per))));m=max(10,min(5000,int(str(self.maximum))))
  except:return await i.response.send_message('❌ Enter valid numbers.',ephemeral=True)
  self.bot.db.set_guild(self.gid,results_per_page=p,max_search_results=m);await i.response.send_message(f'✅ Search settings saved: **{p}/page**, **{m} max**.',ephemeral=True)

class CashModal(discord.ui.Modal,title='Cash App / Manual Payment'):
 cashtag=discord.ui.TextInput(label='Cashtag',placeholder='$YourTag');instructions=discord.ui.TextInput(label='Payment instructions',style=discord.TextStyle.paragraph,required=False)
 def __init__(self,bot,gid):
  super().__init__();self.bot=bot;self.gid=gid;s=bot.payments.settings(gid,'cashapp');self.cashtag.default=s.get('cashtag','');self.instructions.default=s.get('instructions','')
 async def on_submit(self,i):self.bot.payments.save_settings(self.gid,'cashapp',True,{'cashtag':str(self.cashtag),'instructions':str(self.instructions)});await i.response.send_message('✅ Cash App/manual payments enabled and saved.',ephemeral=True)

class PlanModal(discord.ui.Modal,title='Create / Update Subscription Plan'):
 name=discord.ui.TextInput(label='Plan name',placeholder='Monthly');price=discord.ui.TextInput(label='Price',placeholder='25.00');days=discord.ui.TextInput(label='Duration days (0 = lifetime)',placeholder='30');grace=discord.ui.TextInput(label='Grace days',default='7');ids=discord.ui.TextInput(label='Stripe Price ID | PayPal Plan ID',required=False)
 def __init__(self,db,gid):super().__init__();self.db=db;self.gid=gid
 async def on_submit(self,i):
  try:cents=round(float(str(self.price))*100);days=int(str(self.days));grace=max(0,int(str(self.grace)))
  except:return await i.response.send_message('❌ Invalid price/duration/grace.',ephemeral=True)
  ids=[x.strip() for x in str(self.ids).split('|')];stripe=ids[0] if ids and ids[0] else None;paypal=ids[1] if len(ids)>1 and ids[1] else None
  self.db.execute('INSERT INTO subscription_plans(guild_id,name,price_cents,duration_days,lifetime,grace_days,stripe_price_id,paypal_plan_id) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(guild_id,name) DO UPDATE SET price_cents=excluded.price_cents,duration_days=excluded.duration_days,lifetime=excluded.lifetime,grace_days=excluded.grace_days,stripe_price_id=excluded.stripe_price_id,paypal_plan_id=excluded.paypal_plan_id,enabled=1',(self.gid,str(self.name),cents,None if days==0 else days,1 if days==0 else 0,grace,stripe,paypal));await i.response.send_message('✅ Subscription plan saved.',ephemeral=True)

class LicenseActionModal(discord.ui.Modal,title='License Administration'):
 code=discord.ui.TextInput(label='License code',placeholder='420V-...');action=discord.ui.TextInput(label='Action: revoke / enable / extend',placeholder='revoke');days=discord.ui.TextInput(label='Days to extend (extend only)',required=False,default='30')
 def __init__(self,bot,gid):super().__init__();self.bot=bot;self.gid=gid
 async def on_submit(self,i):
  from datetime import datetime,timedelta,timezone
  c=str(self.code).strip().upper();r=self.bot.db.one('SELECT * FROM licenses WHERE code=? AND guild_id=?',(c,self.gid))
  if not r:return await i.response.send_message('❌ License not found.',ephemeral=True)
  a=str(self.action).lower().strip()
  if a=='revoke':self.bot.db.execute("UPDATE licenses SET status='revoked' WHERE code=?",(c,))
  elif a=='enable':self.bot.db.execute("UPDATE licenses SET status='active' WHERE code=?",(c,))
  elif a=='extend':
   try:d=max(1,int(str(self.days)));base=datetime.fromisoformat(r['expires_at']) if r['expires_at'] else datetime.now(timezone.utc);self.bot.db.execute('UPDATE licenses SET expires_at=?,status=\'active\' WHERE code=?',((base+timedelta(days=d)).isoformat(),c))
   except:return await i.response.send_message('❌ Invalid extension days.',ephemeral=True)
  else:return await i.response.send_message('Use `revoke`, `enable`, or `extend`.',ephemeral=True)
  self.bot.db.audit(self.gid,i.user.id,'license_admin',f'{a} license ending {c[-6:]}');await i.response.send_message(f'✅ License action **{a}** completed.',ephemeral=True)

class RemoteServerModal(discord.ui.Modal,title='Add / Update Remote File Server'):
 name=discord.ui.TextInput(label='Server name',placeholder='Main File Server',max_length=80)
 manifest=discord.ui.TextInput(label='HTTPS manifest URL',placeholder='https://files.example.com/420vault-manifest.json',max_length=1000)
 token=discord.ui.TextInput(label='Bearer token (optional)',required=False,max_length=1000)
 def __init__(self,bot,gid):super().__init__();self.bot=bot;self.gid=gid
 async def on_submit(self,i):
  url=str(self.manifest).strip()
  if not url.lower().startswith('https://'):return await i.response.send_message('For v5.5 remote servers, use an HTTPS manifest URL.',ephemeral=True)
  self.bot.db.execute('INSERT INTO remote_sources(guild_id,name,manifest_url,auth_token) VALUES(?,?,?,?) ON CONFLICT(guild_id,name) DO UPDATE SET manifest_url=excluded.manifest_url,auth_token=excluded.auth_token,enabled=1',(self.gid,str(self.name).strip(),url,str(self.token).strip() or None))
  await i.response.send_message('✅ Remote server profile saved. Use **Test & Sync** next.',ephemeral=True)

class SectionSelect(discord.ui.Select):
 def __init__(self,parent):super().__init__(placeholder='Choose an administration section…',options=[discord.SelectOption(label=l,value=v,emoji=e) for v,l,e in SECTIONS],row=0,custom_id=f'420admin:section:{parent.gid}');self.dashboard=parent
 async def callback(self,i):
  await i.response.defer();self.dashboard.section=self.values[0];self.dashboard.build();emb=await asyncio.to_thread(self.dashboard.embed);await i.edit_original_response(embed=emb,view=self.dashboard)

class ActionButton(discord.ui.Button):
 def __init__(self,label,emoji,action,style=discord.ButtonStyle.secondary,row=1,gid=0):super().__init__(label=label,emoji=emoji,style=style,row=row,custom_id=f'420admin:{gid}:{action}');self.action=action
 async def callback(self,i):await self.view.run_action(i,self.action)

class AdminView(discord.ui.View):
 def __init__(self,bot,gid,section='overview'):
  super().__init__(timeout=None);self.bot=bot;self.db=bot.db;self.gid=gid;self.section=section;self.db.seed_plans(gid);self.build()
 async def interaction_check(self,i):
  if await asyncio.to_thread(admin_ok,i,self.gid):return True
  await i.response.send_message('Administrator access required.',ephemeral=True);return False
 def build(self):
  self.clear_items();self.add_item(SectionSelect(self));A=self.add_item
  actions={
   'overview':[('Refresh','🔄','refresh',discord.ButtonStyle.primary)],
   'drive':[('Save Drive Folder','🗂️','drive_config',discord.ButtonStyle.primary),('OAuth Setup','🔐','drive_oauth',discord.ButtonStyle.primary),('Test Connection','🔌','drive_test',discord.ButtonStyle.secondary),('Sync Metadata','🔄','drive_sync',discord.ButtonStyle.success),('Status','📊','drive_status',discord.ButtonStyle.secondary),('Parse ZIP/RAR','🗜️','drive_archives',discord.ButtonStyle.secondary),('Disconnect','⛔','drive_disconnect',discord.ButtonStyle.danger)],
   'vault':[('Configure Path','🗂️','vault_path',discord.ButtonStyle.primary),('Test','🔌','vault_test',discord.ButtonStyle.secondary),('Scan Changes','🔄','vault_scan',discord.ButtonStyle.success),('Full Reindex','🧱','vault_full',discord.ButtonStyle.danger),('Stats','📊','vault_stats',discord.ButtonStyle.secondary)],
   'remote':[('Add / Update Server','➕','remote_add',discord.ButtonStyle.primary),('Test & Sync','🔌','remote_sync',discord.ButtonStyle.success),('Server List','📋','remote_list',discord.ButtonStyle.secondary)],
   'links':[('New Web Scrape','🌐','new_scrape',discord.ButtonStyle.success),('Managed Lists','📚','link_lists',discord.ButtonStyle.primary),('Recent Jobs','📊','scrape_jobs',discord.ButtonStyle.secondary),('Import Help','📥','import_help',discord.ButtonStyle.secondary)],
   'search':[('Search Settings','⚙️','search_settings',discord.ButtonStyle.primary),('Toggle Downloads','📦','toggle_downloads',discord.ButtonStyle.secondary),('Reload Link Lists','🔄','reload_links',discord.ButtonStyle.secondary)],
   'channels':[('Open Channel Setup','📺','setup',discord.ButtonStyle.primary)],
   'roles':[('Configure Access Roles','👥','access_roles',discord.ButtonStyle.primary),('Create Required Roles','➕','create_roles',discord.ButtonStyle.success),('Sync My Roles','🔄','sync_roles',discord.ButtonStyle.secondary)],
   'tos':[('Set Terms Channel','📺','tos_channel',discord.ButtonStyle.primary),('Publish Terms Panel','📜','tos_publish',discord.ButtonStyle.success),('Toggle Terms Gate','🔒','tos_toggle',discord.ButtonStyle.danger),('Verification Stats','📊','tos_stats',discord.ButtonStyle.secondary),('Apply Server Gate','🚪','tos_permissions',discord.ButtonStyle.danger)],
   'licensing':[('Manage License','🔑','license_manage',discord.ButtonStyle.primary),('Recent Licenses','📋','license_list',discord.ButtonStyle.secondary)],
   'subscriptions':[('Create / Update Plan','➕','plan_edit',discord.ButtonStyle.primary),('Plan List','📅','plan_list',discord.ButtonStyle.secondary)],
   'payments':[('Cash App','💵','cash',discord.ButtonStyle.primary),('Toggle Stripe','💳','stripe',discord.ButtonStyle.secondary),('Toggle PayPal','🅿️','paypal',discord.ButtonStyle.secondary),('Provider Status','📡','provider_status',discord.ButtonStyle.secondary)],
   'transactions':[('Recent Transactions','🧾','tx_list',discord.ButtonStyle.primary),('Pending Manual','⏳','tx_pending',discord.ButtonStyle.secondary)],
   'security':[('Toggle Licensing','🔐','toggle_licensing',discord.ButtonStyle.danger),('Security Status','🛡️','security_status',discord.ButtonStyle.secondary)],
   'logs':[('Recent Audit Log','📜','audit',discord.ButtonStyle.primary)],
   'diagnostics':[('Run Diagnostics','🩺','diagnostics',discord.ButtonStyle.primary),('Refresh','🔄','refresh',discord.ButtonStyle.secondary)]}
  for idx,(l,e,a,s) in enumerate(actions.get(self.section,[])):A(ActionButton(l,e,a,s,1+(idx//5),self.gid))
 def embed(self):
  s=self.db.guild(self.gid);x=self.db.vault_stats(self.gid);title=dict((v,l) for v,l,e in SECTIONS)[self.section];e=discord.Embed(title=f'🛠️ 420Vault Admin • {title}',description='Use the menu above to move between control panels. Changes are saved to SQLite unless marked as environment secrets.')
  if self.section=='overview':
   e.add_field(name='Vault',value=('🟢 Configured' if s.get('vault_path') else '🔴 Not configured'));e.add_field(name='SQLite Index',value=f'{x["files"]:,} files\n{x["folders"]:,} folders');e.add_field(name='Downloads',value='✅ Enabled' if s['downloads_enabled'] else '❌ Disabled');e.add_field(name='Licensing',value='🔒 Enforced' if s['licensing_enabled'] else '⚠️ Disabled');e.add_field(name='Search',value=f'{s["results_per_page"]}/page • {s["max_search_results"]} max');e.add_field(name='Subscriptions',value=str(self.db.one('SELECT COUNT(*) n FROM subscription_plans WHERE guild_id=? AND enabled=1',(self.gid,))['n']))
  elif self.section=='drive':
   r=self.db.one('SELECT * FROM drive_sources WHERE guild_id=?',(self.gid,));cs=self.bot.google_drive.credentials_status();oauth=all(cs.values())
   e.description='Set up Google Drive in any order. Save the Drive folder first even before OAuth exists, then add OAuth credentials and use Test Connection.'
   e.add_field(name='OAuth',value='🟢 Configured' if oauth else '🔴 Missing credentials')
   e.add_field(name='Drive Search',value='🟢 Connected' if r and r['enabled'] else '⚪ Not configured')
   e.add_field(name='Root Folder',value=(f'**{r["root_name"]}**\n`{r["root_file_id"]}`' if r else 'Not selected'),inline=False)
   e.add_field(name='Index',value=(f'{r["item_count"]:,} files/folders' if r else '0 files/folders'))
   e.add_field(name='Last Sync',value=(r['last_sync'] or 'Never') if r else 'Never')
   e.add_field(name='Status',value=(r['last_status'] or 'unknown') if r else 'not configured')
   e.add_field(name='OAuth',value=('🟢 Credentials saved' if oauth else '🟡 Not complete — use **OAuth Setup**'),inline=False);e.add_field(name='Saved folder',value=(f'`{r["root_file_id"]}`' if r else 'Not saved'),inline=False)
  elif self.section=='vault':e.add_field(name='Root',value=f'`{s["vault_path"]}`' if s.get('vault_path') else 'Not configured',inline=False);e.add_field(name='Connection',value=('🟢 Last scan online' if x.get('status')=='online' else ('🟡 Configured / not scanned' if s.get('vault_path') else '🔴 Not configured')));e.add_field(name='Index',value=f'{x["files"]:,} files • {x["folders"]:,} folders • {fmt_bytes(x["size"])}',inline=False);e.add_field(name='Last scan',value=x['last_scan'] or 'Never')
  elif self.section=='links':
   rows=LinkLibrary(self.db).lists(self.gid);total=self.db.one('SELECT COUNT(*) n FROM links WHERE guild_id=?',(self.gid,))['n'];jobs=self.db.one("SELECT COUNT(*) n FROM scrape_jobs WHERE guild_id=? AND status='running'",(self.gid,))['n'];e.add_field(name='Managed lists',value=str(len(rows)));e.add_field(name='Unique indexed links',value=f'{total:,}');e.add_field(name='Running jobs',value=str(jobs));e.add_field(name='Workflow',value='Scrape any public HTTP/HTTPS site → result GUI → create a new list or merge into an existing list → incremental FTS index.',inline=False)
  elif self.section=='remote':
   rows=self.db.all('SELECT r.*,COUNT(i.id) n FROM remote_sources r LEFT JOIN remote_items i ON i.source_id=r.id WHERE r.guild_id=? GROUP BY r.id ORDER BY r.name',(self.gid,));e.description='Connect HTTPS file servers through a configurable JSON manifest. Temporary server outages preserve the last index.';e.add_field(name='Servers',value=str(len(rows)));e.add_field(name='Indexed items',value=f'{sum(int(r["n"]) for r in rows):,}');e.add_field(name='Profiles',value='\n'.join(f'**{r["name"]}** • {r["last_status"]} • {r["n"]:,} items' for r in rows[:10]) or 'None configured',inline=False)
  elif self.section=='search':e.add_field(name='Results/page',value=str(s['results_per_page']));e.add_field(name='Maximum',value=str(s['max_search_results']));e.add_field(name='Downloads',value='Enabled' if s['downloads_enabled'] else 'Disabled');e.add_field(name='Allowed channels',value=' '.join(f'<#{z}>' for z in self.db.channels(self.gid,'search')) or 'All channels',inline=False)
  elif self.section=='channels':e.description='Configure search/delivery, license activation and audit channels.'
  elif self.section=='roles':
   def rr(k):
    rid=s.get(k);r=self.bot.get_guild(self.gid).get_role(rid) if rid and self.bot.get_guild(self.gid) else None
    return r.mention if r else 'Not mapped'
   e.description='Portable role mapping. 420Vault stores Discord role IDs and never guesses a role from its name. Map existing roles, or explicitly create only the three required core roles.'
   e.add_field(name='TOS Accepted',value=rr('verified_role_id'));e.add_field(name='Verified',value=rr('member_role_id'));e.add_field(name='Paid Member',value=rr('subscribed_role_id'));e.add_field(name='Unverified',value=rr('unverified_role_id'));e.add_field(name='Beta Tester',value=rr('beta_role_id'));e.add_field(name='Custom bot admin (optional)',value=rr('overseer_role_id'))
  elif self.section=='tos':
   e.add_field(name='Gate',value='🔒 Required' if s.get('tos_enabled',1) else '⚠️ Disabled');e.add_field(name='Terms channel',value=f'<#{s["tos_channel_id"]}>' if s.get('tos_channel_id') else 'Not configured');e.add_field(name='Version',value=TOS_VERSION);e.add_field(name='Knowledge check',value=f'{s.get("tos_pass_percent") or 80}% pass • {s.get("tos_min_read_seconds") or 60}s minimum read time • {s.get("tos_max_kicks") or 3} kick/rejoin failures before ban',inline=False)
  elif self.section=='licensing':e.add_field(name='Active',value=str(self.db.one("SELECT COUNT(*) n FROM licenses WHERE guild_id=? AND status='active'",(self.gid,))['n']));e.add_field(name='Revoked / expired',value=str(self.db.one("SELECT COUNT(*) n FROM licenses WHERE guild_id=? AND status!='active'",(self.gid,))['n']));e.add_field(name='Activation',value='DM button workflow • no activation command',inline=False)
  elif self.section=='subscriptions':e.description='Create/update plans and inspect the enabled catalog. Defaults remain editable.'
  elif self.section=='payments':
   for p in ('cashapp','stripe','paypal'):e.add_field(name=p.title(),value='✅ Enabled' if self.bot.payments.settings(self.gid,p).get('enabled') else '❌ Disabled')
   e.add_field(name='Secrets',value='Stripe/PayPal secrets remain outside Discord and are never displayed.',inline=False)
  elif self.section=='transactions':e.add_field(name='Total',value=str(self.db.one('SELECT COUNT(*) n FROM transactions WHERE guild_id=?',(self.gid,))['n']));e.add_field(name='Pending manual',value=str(self.db.one("SELECT COUNT(*) n FROM transactions WHERE guild_id=? AND status='pending_manual'",(self.gid,))['n']))
  elif self.section=='security':e.add_field(name='Mandatory licensing',value='Enabled' if s['licensing_enabled'] else 'Disabled');e.add_field(name='Signed licenses',value='HMAC-SHA256');e.add_field(name='API key',value='Configured' if os.getenv('VAULT_API_KEY') else 'Missing');e.add_field(name='Signing secret',value='Configured' if os.getenv('LICENSE_SIGNING_SECRET') else 'Missing')
  elif self.section=='logs':e.description='Administrative actions are recorded without exposing license secrets or payment credentials.'
  elif self.section=='diagnostics':e.add_field(name='Database',value='SQLite / WAL');e.add_field(name='Vault',value='Configured' if s.get('vault_path') else 'Not configured');e.add_field(name='Links loaded',value=f'{len(self.bot.link_search.links):,}')
  e.set_footer(text='420Vault v5.5.6 • Admin GUI');return e
 async def run_action(self,i,a):
  if a=='refresh':
   await i.response.defer();emb=await asyncio.to_thread(self.embed);return await i.edit_original_response(embed=emb,view=self)
  if a=='drive_config':return await i.response.send_modal(DriveRootModal(self.bot,self.gid))
  if a=='drive_oauth':return await i.response.send_modal(DriveOAuthModal(self.bot,self.gid))
  if a=='drive_test':
   r=self.db.one('SELECT * FROM drive_sources WHERE guild_id=?',(self.gid,))
   if not r:return await i.response.send_message('☁️ Save a Drive folder first with **Save Drive Folder**.',ephemeral=True)
   if not all(self.bot.google_drive.credentials_status().values()):return await i.response.send_message('🔐 Drive folder is saved, but OAuth is not complete. Use **OAuth Setup**, then test again.',ephemeral=True)
   await i.response.defer(ephemeral=True,thinking=True)
   try:
    m=await self.bot.google_drive.test_connection(self.gid);return await i.followup.send(f'🟢 **Google Drive connection OK**\nRoot: **{m["name"]}**\nFolder ID: `{m["id"]}`',ephemeral=True)
   except Exception as e:return await i.followup.send(f'🔴 Google Drive connection failed: `{str(e)[:700]}`',ephemeral=True)
  if a=='drive_sync':
   r=await asyncio.to_thread(self.db.one,'SELECT 1 FROM drive_sources WHERE guild_id=? AND enabled=1',(self.gid,))
   if not r:return await i.response.send_message('Configure a Google Drive root first.',ephemeral=True)
   try:
    started=await self.bot.google_drive.start_sync(self.gid)
    if not started:return await i.response.send_message('🟡 A Google Drive metadata sync is already running. Use **Status** to watch progress.',ephemeral=True)
    await asyncio.to_thread(self.db.audit,self.gid,i.user.id,'drive_sync_started','Google Drive metadata sync started in background')
    return await i.response.send_message('🟡 **Google Drive metadata sync started in the background.**\nThe bot will remain responsive. Use **Status** to watch the indexed count and progress.',ephemeral=True)
   except Exception as e:return await i.response.send_message(f'❌ Google Drive sync could not start: `{str(e)[:700]}`',ephemeral=True)
  if a=='drive_status':
   r=await asyncio.to_thread(self.db.one,'SELECT * FROM drive_sources WHERE guild_id=?',(self.gid,))
   if not r:return await i.response.send_message('Google Drive is not configured.',ephemeral=True)
   p=self.bot.google_drive.sync_progress(self.gid);extra=''
   if p.get('running') or p.get('status') in ('syncing','finalizing'):
    extra=f'\nElapsed: **{p.get("elapsed",0)//60:02d}:{p.get("elapsed",0)%60:02d}**\nCurrent: `{str(p.get("current") or "-")[:300]}`'
   if p.get('error'):extra+=f'\nError: `{str(p["error"])[:500]}`'
   return await i.response.send_message(f'☁️ **Google Drive Status**\nRoot: **{r["root_name"]}**\nStatus: **{r["last_status"] or p.get("status") or "unknown"}**\nIndexed: **{r["item_count"]:,}**\nLast sync: **{r["last_sync"] or "Never"}**{extra}',ephemeral=True)
  if a=='drive_archives':
   r=await asyncio.to_thread(self.db.one,'SELECT 1 FROM drive_sources WHERE guild_id=? AND enabled=1',(self.gid,))
   if not r:return await i.response.send_message('Configure and sync Google Drive first.',ephemeral=True)
   started=await self.bot.google_drive.start_archive_parse(self.gid)
   if not started:return await i.response.send_message('🟡 ZIP/RAR parsing is already running. Use **Status** to monitor it.',ephemeral=True)
   await asyncio.to_thread(self.db.audit,self.gid,i.user.id,'drive_archive_parse_started','Google Drive ZIP/RAR content indexing started')
   return await i.response.send_message('🗜️ **ZIP/RAR parsing started in the background.** The bot downloads each eligible archive temporarily, indexes the filenames inside it, then deletes the temporary copy. Search hits inside an archive will download the **full original ZIP/RAR**.',ephemeral=True)
  if a=='drive_disconnect':
   r=self.db.one('SELECT * FROM drive_sources WHERE guild_id=?',(self.gid,))
   if not r:return await i.response.send_message('Google Drive is already disconnected.',ephemeral=True)
   self.db.execute('UPDATE drive_sources SET enabled=0,last_status=? WHERE guild_id=?',('disconnected',self.gid));self.db.audit(self.gid,i.user.id,'drive_disconnect','disabled Google Drive search source')
   return await i.response.edit_message(embed=self.embed(),view=self)
  if a=='vault_path':return await i.response.send_modal(VaultModal(self.bot,self.gid))
  if a=='vault_test':
   await i.response.defer(ephemeral=True,thinking=True)
   p=(await asyncio.to_thread(self.db.guild,self.gid)).get('vault_path')
   ok=bool(p) and await asyncio.to_thread(Path(p).is_dir)
   return await i.followup.send(('🟢 Vault Online' if ok else '🔴 Vault Missing / disconnected')+(f'\n`{p}`' if p else ''),ephemeral=True)
  if a in ('vault_scan','vault_full'):
   await i.response.defer(ephemeral=True,thinking=True)
   p=(await asyncio.to_thread(self.db.guild,self.gid)).get('vault_path')
   ok=bool(p) and await asyncio.to_thread(Path(p).is_dir)
   if not ok:return await i.followup.send('🔴 Vault missing/disconnected. Existing SQLite index was preserved.',ephemeral=True)
   started=_start_vault_scan(self.bot,self.gid,p,a=='vault_full',i.user.id)
   if not started:return await i.followup.send('🟡 A physical Vault scan is already running. Use **Stats** to watch progress.',ephemeral=True)
   return await i.followup.send(('🟠 **Full reindex**' if a=='vault_full' else '🟢 **Scan changes**')+' started in the background. The bot will remain responsive; use **Stats** for progress.',ephemeral=True)
  if a=='vault_stats':
   await i.response.defer(ephemeral=True,thinking=True)
   x=await asyncio.to_thread(self.db.vault_stats,self.gid);p=_VAULT_PROGRESS.get(self.gid,{})
   extra=''
   if _vault_running(self.gid):
    elapsed=max(0,int(asyncio.get_running_loop().time()-p.get('started',asyncio.get_running_loop().time())))
    extra=f'\nStatus: **{p.get("status","scanning")}**\nProcessed: **{p.get("processed",0):,}**\nElapsed: **{elapsed//60:02d}:{elapsed%60:02d}**\nCurrent: `{str(p.get("current") or "-")[:300]}`'
   elif p.get('status')=='failed':extra=f'\nStatus: **failed**\nError: `{str(p.get("error"))[:500]}`'
   return await i.followup.send(f'📊 **SQLite Vault Index**\nFiles: {x["files"]:,}\nFolders: {x["folders"]:,}\nSize: {fmt_bytes(x["size"])}\nLast scan: {x["last_scan"] or "Never"}{extra}',ephemeral=True)
  if a=='new_scrape':return await i.response.send_modal(ScrapeModal(self.bot,self.gid))
  if a=='link_lists':
   rows=LinkLibrary(self.db).lists(self.gid);txt='\n'.join(f'`#{r["id"]}` **{r["name"]}** • {r["link_count"]:,} links • {r["source_type"]}' for r in rows[:20]) or 'No managed link lists yet.';return await i.response.send_message(txt,ephemeral=True)
  if a=='scrape_jobs':
   rs=self.db.all('SELECT * FROM scrape_jobs WHERE guild_id=? ORDER BY id DESC LIMIT 15',(self.gid,));txt='\n'.join(f'`#{r["id"]}` **{r["status"]}** • {r["pages_crawled"]:,} pages • {r["links_found"]:,} links • {r["target_url"][:80]}' for r in rs) or 'No scraper jobs.';return await i.response.send_message(txt,ephemeral=True)
  if a=='import_help':return await i.response.send_message('📥 **External Link List Import**\nAttach a `.txt` file and run `420_importlinks <list name>`. The file is normalized, deduplicated and incrementally indexed into the same managed Link Library used by built-in scrapes.',ephemeral=True)
  if a=='remote_add':return await i.response.send_modal(RemoteServerModal(self.bot,self.gid))
  if a=='remote_list':
   rs=self.db.all('SELECT * FROM remote_sources WHERE guild_id=? ORDER BY name',(self.gid,));txt='\n'.join(f'`#{r["id"]}` **{r["name"]}** • {r["last_status"]} • last sync {r["last_sync"] or "never"}' for r in rs) or 'No remote servers configured.';return await i.response.send_message(txt,ephemeral=True)
  if a=='remote_sync':
   rs=self.db.all('SELECT * FROM remote_sources WHERE guild_id=? AND enabled=1 ORDER BY id',(self.gid,))
   if not rs:return await i.response.send_message('Add a remote server first.',ephemeral=True)
   await i.response.defer(ephemeral=True,thinking=True);svc=RemoteServers(self.db);out=[]
   for r in rs:
    try:n=await svc.sync(self.gid,r['id']);out.append(f'🟢 **{r["name"]}** — {n:,} items')
    except Exception as ex:self.db.execute("UPDATE remote_sources SET last_status='offline' WHERE id=?",(r['id'],));out.append(f'🔴 **{r["name"]}** — {type(ex).__name__}: {str(ex)[:180]}')
   return await i.followup.send('\n'.join(out),ephemeral=True)
  if a=='search_settings':return await i.response.send_modal(SearchSettingsModal(self.bot,self.gid))
  if a=='toggle_downloads':
   s=self.db.guild(self.gid);self.db.set_guild(self.gid,downloads_enabled=0 if s['downloads_enabled'] else 1);return await i.response.edit_message(embed=self.embed(),view=self)
  if a=='reload_links':
   await i.response.defer(ephemeral=True,thinking=True);n=await asyncio.to_thread(self.bot.link_search.reload);return await i.followup.send(f'✅ Reloaded **{n:,}** unique links.',ephemeral=True)
  if a=='setup':return await i.response.send_message(embed=discord.Embed(title='📺 Channel Setup',description='Configure search/delivery, activation and audit channels. Legacy admin/member role selectors remain available here for compatibility.'),view=SetupView(self.bot,self.gid),ephemeral=True)
  if a=='access_roles':return await i.response.send_message('👥 Map this server’s existing roles to 420Vault functions. Role IDs are saved; names can be changed later without breaking access.',view=AccessRoleSetup(self.bot,self.gid),ephemeral=True)
  if a=='create_roles':
   from app.services.server_bootstrap import create_recommended_roles
   await i.response.defer(ephemeral=True,thinking=True)
   try:
    rows=await create_recommended_roles(self.bot,i.guild)
    lines=[f'{"Created" if made else "Already configured"}: {role.mention}' for role,made in rows.values()]
    return await i.followup.send('✅ Required core roles are ready.\n'+'\n'.join(lines)+'\n\nThe recommended set includes TOS Accepted, Verified, Unverified, Paid Member, and Beta Tester. Custom admin roles remain optional and are never auto-created.',ephemeral=True)
   except (discord.Forbidden,discord.HTTPException) as exc:return await i.followup.send(f'❌ Could not create roles: `{type(exc).__name__}`. Check Manage Roles and role hierarchy.',ephemeral=True)
  if a=='sync_roles':await self.bot.sync_member_access_roles(self.gid,i.user.id);return await i.response.send_message('✅ Your access roles were reconciled.',ephemeral=True)
  if a=='tos_channel':return await i.response.send_message('Choose the Terms / verification channel:',view=TosChannelSetup(self.bot,self.gid),ephemeral=True)
  if a=='tos_toggle':
   st=self.db.guild(self.gid);enabled=0 if st.get('tos_enabled',1) else 1;self.db.set_guild(self.gid,tos_enabled=enabled)
   ur=role_by_setting(i.guild,self.db.guild(self.gid),'unverified_role_id','Unverified')
   if not enabled and ur:
    for ch in i.guild.channels:
     try:await ch.set_permissions(ur,overwrite=None,reason='420Vault Terms gate disabled')
     except (discord.Forbidden,discord.HTTPException):pass
   for m in i.guild.members:
    await self.bot.sync_member_access_roles(self.gid,m.id)
   return await i.response.edit_message(embed=self.embed(),view=self)
  if a=='tos_publish':
   st=self.db.guild(self.gid);ch=i.guild.get_channel(st.get('tos_channel_id')) if st.get('tos_channel_id') else None
   if not isinstance(ch,discord.TextChannel):return await i.response.send_message('Set a valid Terms channel first.',ephemeral=True)
   await publish_tos(self.bot,i.guild,ch);return await i.response.send_message(f'✅ Terms verification panel published in {ch.mention}.',ephemeral=True)
  if a=='tos_stats':
   ok=self.db.one('SELECT COUNT(*) n FROM tos_acceptance WHERE guild_id=? AND tos_version=?',(self.gid,TOS_VERSION))['n'];fail=self.db.one('SELECT COALESCE(SUM(failed_sessions),0) n FROM tos_attempts WHERE guild_id=?',(self.gid,))['n'];return await i.response.send_message(f'📊 Current-version verified: **{ok:,}**\nRecorded failed sessions: **{fail:,}**',ephemeral=True)
  if a=='tos_permissions':
   st=self.db.guild(self.gid);ur=i.guild.get_role(st.get('unverified_role_id')) if st.get('unverified_role_id') else next((r for r in i.guild.roles if r.name.casefold()=='unverified'),None);tc=i.guild.get_channel(st.get('tos_channel_id')) if st.get('tos_channel_id') else None
   if not ur or not isinstance(tc,discord.TextChannel):return await i.response.send_message('Configure the **Unverified** role and Terms channel first.',ephemeral=True)
   await i.response.defer(ephemeral=True,thinking=True);changed=0;failed=0
   for ch in i.guild.channels:
    try:
     if ch.id==tc.id:await ch.set_permissions(ur,view_channel=True,send_messages=True,read_message_history=True,reason='420Vault Terms gate')
     else:await ch.set_permissions(ur,view_channel=False,reason='420Vault Terms gate')
     changed+=1
    except (discord.Forbidden,discord.HTTPException):failed+=1
   return await i.followup.send(f'✅ Terms gate permissions applied to **{changed}** channels. Failed: **{failed}**. Unverified members can only see the configured Terms channel until the role is removed.',ephemeral=True)
  if a=='license_manage':return await i.response.send_modal(LicenseActionModal(self.bot,self.gid))
  if a=='license_list':
   rs=self.db.all('SELECT code,status,expires_at,assigned_user_id,activations FROM licenses WHERE guild_id=? ORDER BY created_at DESC LIMIT 10',(self.gid,));txt='\n'.join(f'`…{r["code"][-8:]}` • {r["status"]} • <@{r["assigned_user_id"]}> • {r["expires_at"] or "Lifetime"}' for r in rs) or 'No licenses.';return await i.response.send_message(txt,ephemeral=True)
  if a=='plan_edit':return await i.response.send_modal(PlanModal(self.db,self.gid))
  if a=='plan_list':
   rs=self.db.all('SELECT * FROM subscription_plans WHERE guild_id=? ORDER BY price_cents',(self.gid,));txt='\n'.join(f'**{r["name"]}** — ${r["price_cents"]/100:.2f} • {"Lifetime" if r["lifetime"] else str(r["duration_days"])+" days"} • {"ON" if r["enabled"] else "OFF"}' for r in rs);return await i.response.send_message(txt,ephemeral=True)
  if a=='cash':return await i.response.send_modal(CashModal(self.bot,self.gid))
  if a in ('stripe','paypal'):
   s=self.bot.payments.settings(self.gid,a);cfg={k:v for k,v in s.items() if k!='enabled'};self.bot.payments.save_settings(self.gid,a,not s.get('enabled'),cfg);return await i.response.edit_message(embed=self.embed(),view=self)
  if a=='provider_status':
   return await i.response.send_message(f'**Stripe**: {"enabled" if self.bot.payments.settings(self.gid,"stripe").get("enabled") else "disabled"} • secret {"configured" if os.getenv("STRIPE_SECRET_KEY") else "missing"}\n**PayPal**: {"enabled" if self.bot.payments.settings(self.gid,"paypal").get("enabled") else "disabled"} • credentials {"configured" if os.getenv("PAYPAL_CLIENT_SECRET") else "missing"}\n**Cash App**: {"enabled" if self.bot.payments.settings(self.gid,"cashapp").get("enabled") else "disabled"}',ephemeral=True)
  if a in ('tx_list','tx_pending'):
   sql='SELECT * FROM transactions WHERE guild_id=? '+("AND status='pending_manual' " if a=='tx_pending' else '')+'ORDER BY id DESC LIMIT 15';rs=self.db.all(sql,(self.gid,));txt='\n'.join(f'`#{r["id"]}` <@{r["user_id"]}> • {r["provider"]} • ${((r["amount_cents"] or 0)/100):.2f} • **{r["status"]}**' for r in rs) or 'No transactions.';return await i.response.send_message(txt,ephemeral=True)
  if a=='toggle_licensing':
   s=self.db.guild(self.gid);self.db.set_guild(self.gid,licensing_enabled=0 if s['licensing_enabled'] else 1);self.db.audit(self.gid,i.user.id,'licensing_toggle','changed mandatory licensing setting');return await i.response.edit_message(embed=self.embed(),view=self)
  if a=='security_status':return await i.response.send_message('🛡️ **Security**\nSigned licenses: HMAC-SHA256\nRaw card storage: disabled\nProvider secrets: environment-only\nWebhook events: idempotency table enabled\nAdmin actions: audited',ephemeral=True)
  if a=='audit':
   rs=self.db.all('SELECT * FROM audit_log WHERE guild_id=? ORDER BY id DESC LIMIT 15',(self.gid,));txt='\n'.join(f'`#{r["id"]}` <@{r["user_id"]}> • **{r["action"]}** • {r["created_at"]}' for r in rs) or 'No audit events.';return await i.response.send_message(txt,ephemeral=True)
  if a=='diagnostics':
   await i.response.defer(ephemeral=True,thinking=True)
   s=await asyncio.to_thread(self.db.guild,self.gid);x=await asyncio.to_thread(self.db.vault_stats,self.gid);online=bool(s.get('vault_path')) and await asyncio.to_thread(Path(s['vault_path']).is_dir);channels=await asyncio.to_thread(self.db.channels,self.gid,'search')
   return await i.followup.send(f'🩺 **Diagnostics**\nSQLite: OK\nVault: {"Online" if online else "Offline"}\nIndexed: {x["files"]:,} files / {x["folders"]:,} folders\nLinks: {len(self.bot.link_search.links):,}\nSearch channels: {len(channels)}\nLicense channel: {s.get("license_channel_id") or "Not set"}',ephemeral=True)

