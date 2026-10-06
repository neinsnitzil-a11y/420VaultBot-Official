from __future__ import annotations
import random,time
import discord

TOS_VERSION='2026-09-23-v2'
TOS_TEXT="""# 420Vault Community Terms of Service & Distribution Rules

**Purpose.** 420Vault is a music-production resource, indexing, delivery and subscription system for plugins, drum kits, one-shots, MIDI, presets, expansion banks, project files and related production resources. Access to the Discord server and 420Vault is conditional on accepting these terms and passing the comprehension check.

**1 — Rights and lawful use.** You may only upload, submit, request, download, distribute, share or use material when you have the rights or permission required to do so. A listing, link, index entry or bot result is not a representation that a file is licensed for every use. Third-party trademarks, copyrights and licenses remain with their respective owners. Do not use 420Vault to infringe copyright, bypass paid licensing, traffic stolen credentials, distribute malware, or misrepresent ownership.

**2 — Music-production resources.** Plugins, drum kits, samples, loops, one-shots, MIDI, presets, banks, expansions, DAW projects and archives may have separate developer/creator licenses. You are responsible for checking the applicable license before commercial use, redistribution, resale, modification or public release. Do not resell or repackage another creator's work as your own.

**3 — Links and external sites.** Search results may point to third-party websites. 420Vault does not control those sites and cannot guarantee their availability, safety, accuracy or licensing. Do not use the scraper or link tools against private/internal networks, to bypass authentication, or in a way that violates applicable law or a site's access controls.

**4 — Accounts and access.** Your Discord account and 420Vault license are for you. Do not share, sell, transfer, clone or bypass licenses, subscriptions, verification or access controls. Beta Tester access is a server-granted testing privilege and may provide user-command access without a paid subscription. A configured custom bot-admin role has bot-management authority. Role privileges do not waive these Terms.

**5 — Payments and subscriptions.** Paid access is granted only after the configured payment provider or an authorized administrator confirms payment. Recurring plans remain subject to their billing cycle. Failed renewals may enter the configured grace period; when that period ends without successful payment, subscription access and the associated subscription license may be revoked and the configured paid-member role removed. Provider checkout pages—not Discord messages—handle card details. Never send card numbers or CVV to staff or through Discord.

**6 — Security and abuse.** No malware, credential theft, scams, payment fraud, unauthorized access, denial-of-service activity, attempts to defeat rate limits, scraping of private systems, or attempts to exploit the bot/server. Do not probe staff infrastructure, secrets, tokens, payment credentials or other members' private information.

**7 — Community conduct.** Do not impersonate staff, falsify payment proof, harass users, spam commands, intentionally poison indexes, submit deceptive links, or abuse download/scraper resources. Staff may remove unsafe links/files, restrict features, revoke privileges, or moderate accounts to protect the service and community.

**8 — Availability and files.** External links can disappear and physical Vault storage can be offline. The service is provided without a promise that every indexed item remains available. Never assume an archive or executable is safe merely because it appears in search; use appropriate security practices before opening third-party content.

**9 — Privacy and records.** The bot may retain Discord user/server IDs, acceptance version/time, quiz outcome, licenses, subscriptions, transactions, moderation/audit events and operational metadata needed to provide and secure the service. Raw payment-card numbers and CVV are not to be stored by 420Vault; configured payment processors handle payment credentials.

**10 — Verification and enforcement.** You must read these Terms, pass the randomized comprehension check, and explicitly accept the current version before using protected server/bot features. Failed or declined verification can result in removal from the server. Repeated failed verification sessions are tracked by Discord user ID; after the configured rejoin allowance, the account can be server-banned. Discord bots do not receive member IP addresses, so 420Vault does not claim to perform IP bans.

**11 — Changes.** Material Terms updates may require re-verification. Acceptance applies to the displayed Terms version. Continued access after a required update depends on accepting the new version.

**12 — Acknowledgement.** By selecting Accept after the knowledge check, you confirm that you read the Terms, understand the rules above, will respect third-party rights and applicable licenses, will not bypass 420Vault security/payment/access controls, and agree to follow server moderation rules. If you do not agree, decline and leave the server.
"""

QUESTIONS=[
 ('Who is responsible for checking whether a plugin, kit, preset, sample or other resource may be used or redistributed?', ['The user using/distributing it','420Vault automatically guarantees all rights','Discord','Nobody'],0),
 ('Where should card information be entered for a configured online payment?', ['In a staff DM','In the payment provider checkout page','In a public ticket','In the license activation modal'],1),
 ('Does a 420Vault search result guarantee that third-party material is licensed for every use?', ['Yes','Only for Beta Testers','No','Only when it is a ZIP'],2),
 ('What happens to subscription access after an unpaid grace period ends?', ['It becomes lifetime access','Subscription access/license may be revoked','Nothing changes forever','The user becomes an admin'],1),
 ('Can a member share, sell, clone, or bypass their 420Vault license?', ['Yes','Only once','Only with another Discord member','No'],3),
 ('What does the Beta Tester role provide when configured?', ['Free user-command access for testing','Automatic staff ownership','Permission to ignore the TOS','Raw payment access'],0),
 ('Does a configured bot-admin role remove the requirement to follow the Terms?', ['Yes','No','Only for downloads','Only during testing'],1),
 ('What should you assume about a third-party executable or archive found through search?', ['It is automatically safe','It was written by 420Vault','Use appropriate security practices before opening it','It has no license'],2),
 ('What may happen if Physical Vault storage is temporarily offline?', ['The preserved index can remain but delivery waits for storage','Every user becomes admin','All licenses expire','Payment details are exposed'],0),
 ('May the scraper be used to bypass authentication or crawl private/internal systems?', ['Yes, always','Only at night','No','Only with concurrency 1'],2),
 ('What should you do with payment card numbers or CVV?', ['Post them in a ticket','Send them to staff','Enter them only on the configured provider checkout','Put them in a license code'],2),
 ('Does accepting Terms transfer third-party copyrights to you?', ['Yes','No','Only for samples','Only after payment'],1),
 ('Can staff remove unsafe/deceptive links or restrict abusive use?', ['No','Yes','Only Discord can','Only the payment provider can'],1),
 ('Are external links guaranteed to stay available forever?', ['Yes','No','Only ZIP links','Only paid links'],1),
 ('What happens after a material Terms update when re-verification is required?', ['Old acceptance always overrides it','You may need to accept the new version','You become a Beta Tester','Nothing can change'],1),
 ('Should you intentionally spam commands or poison indexes?', ['Yes','Only during testing','No','Only in tickets'],2),
]

_LAST_QUIZ_SIGNATURES={}
_rng=random.SystemRandom()

def fresh_questions(gid,uid,count=5):
 pool=list(QUESTIONS);count=min(max(1,count),len(pool));last=_LAST_QUIZ_SIGNATURES.get((gid,uid))
 chosen=None
 for _ in range(20):
  chosen=_rng.sample(pool,k=count)
  sig=tuple(q[0] for q in chosen)
  if sig!=last:break
 _LAST_QUIZ_SIGNATURES[(gid,uid)]=tuple(q[0] for q in chosen)
 return chosen

def quiz_embed(view):
 q=view.questions[view.index][0]
 e=discord.Embed(title='🧠 420Vault Terms Knowledge Check',description=f'**Question {view.index+1} of {len(view.questions)}**\n\n{q}',color=discord.Color.blurple())
 e.set_footer(text='Questions and answer order are randomized for each verification session.')
 return e

def accepted(db,gid,uid):
 return bool(db.one('SELECT 1 FROM tos_acceptance WHERE guild_id=? AND user_id=? AND tos_version=?',(gid,uid,TOS_VERSION)))

def role_by_setting(guild,settings,key,fallback=None):
 # Portable role mapping: configured Discord role IDs are authoritative.
 # `fallback` is retained only for call-site compatibility; names are never guessed.
 rid=settings.get(key)
 return guild.get_role(int(rid)) if rid else None

class TosStartView(discord.ui.View):
 def __init__(self,bot):super().__init__(timeout=None)
 @discord.ui.button(label='Read & Verify',emoji='📜',style=discord.ButtonStyle.primary,custom_id='420vault:tos:start')
 async def start(self,i,b):
  if not i.guild:return await i.response.send_message('Verification must be completed in the server.',ephemeral=True)
  if accepted(i.client.db,i.guild.id,i.user.id):return await i.response.send_message('✅ You already accepted the current Terms.',ephemeral=True)
  pages=tos_pages(); await i.response.send_message(embed=tos_embed(0,pages),view=TosReadView(i.client,i.guild.id,i.user.id,pages),ephemeral=True)

def tos_pages():
 paras=TOS_TEXT.split('\n\n');pages=[];cur=''
 for para in paras:
  add=para+'\n\n'
  if len(cur)+len(add)>3800:
   pages.append(cur.rstrip());cur=add
  else:cur+=add
 if cur:pages.append(cur.rstrip())
 return pages
def tos_embed(index,pages):
 e=discord.Embed(title='📜 420Vault Terms of Service',description=pages[index],color=discord.Color.dark_green());e.set_footer(text=f'Terms {TOS_VERSION} • Page {index+1}/{len(pages)}');return e
class TosReadView(discord.ui.View):
 def __init__(self,bot,gid,uid,pages):
  super().__init__(timeout=900);self.bot=bot;self.gid=gid;self.uid=uid;self.started=time.monotonic();self.pages=pages;self.page=0
 @discord.ui.button(label='Previous',style=discord.ButtonStyle.secondary,row=0)
 async def prev(self,i,b):
  if i.user.id!=self.uid:return await i.response.send_message('This verification session belongs to another member.',ephemeral=True)
  self.page=max(0,self.page-1);await i.response.edit_message(embed=tos_embed(self.page,self.pages),view=self)
 @discord.ui.button(label='Next',style=discord.ButtonStyle.secondary,row=0)
 async def next(self,i,b):
  if i.user.id!=self.uid:return await i.response.send_message('This verification session belongs to another member.',ephemeral=True)
  self.page=min(len(self.pages)-1,self.page+1);await i.response.edit_message(embed=tos_embed(self.page,self.pages),view=self)
 @discord.ui.button(label='I Finished Reading — Start Check',emoji='🧠',style=discord.ButtonStyle.success,row=1)
 async def quiz(self,i,b):
  if i.user.id!=self.uid:return await i.response.send_message('This verification session belongs to another member.',ephemeral=True)
  sec=int(self.bot.db.guild(self.gid).get('tos_min_read_seconds') or 60);left=sec-int(time.monotonic()-self.started)
  if left>0:return await i.response.send_message(f'📖 Please finish reading the Terms. The knowledge check unlocks in **{left}s**.',ephemeral=True)
  qs=fresh_questions(self.gid,self.uid,5);v=QuizView(self.bot,self.gid,self.uid,qs);await i.response.edit_message(content=None,embed=quiz_embed(v),view=v)
 @discord.ui.button(label='Decline Terms',style=discord.ButtonStyle.danger,row=1)
 async def decline(self,i,b):await fail_session(self.bot,i,self.gid,self.uid,'declined')

class AnswerSelect(discord.ui.Select):
 def __init__(self,parent):
  q,answers,correct=parent.questions[parent.index];order=list(range(len(answers)));_rng.shuffle(order);self.correct_value=str(correct)
  super().__init__(placeholder='Choose the best answer…',options=[discord.SelectOption(label=answers[x][:100],value=str(x)) for x in order]);self.parent_view=parent
 async def callback(self,i):
  v=self.parent_view
  if i.user.id!=v.uid:return await i.response.send_message('This verification session belongs to another member.',ephemeral=True)
  if self.values[0]==self.correct_value:v.correct+=1
  v.index+=1
  if v.index>=len(v.questions):return await v.finish(i)
  v.rebuild();await i.response.edit_message(content=None,embed=quiz_embed(v),view=v)

class QuizView(discord.ui.View):
 def __init__(self,bot,gid,uid,questions):super().__init__(timeout=600);self.bot=bot;self.gid=gid;self.uid=uid;self.questions=questions;self.index=0;self.correct=0;self.rebuild()
 def rebuild(self):self.clear_items();self.add_item(AnswerSelect(self))
 def text(self):return f'🧠 **Question {self.index+1}/{len(self.questions)}**\n\n{self.questions[self.index][0]}'
 async def finish(self,i):
  pct=round(self.correct*100/len(self.questions));need=int(self.bot.db.guild(self.gid).get('tos_pass_percent') or 80)
  if pct<need:return await fail_session(self.bot,i,self.gid,self.uid,f'quiz {pct}%')
  await i.response.edit_message(content=f'✅ Knowledge check passed: **{pct}%**. Review the acknowledgement and explicitly accept.',embed=None,view=AcceptView(self.bot,self.gid,self.uid,pct))

class AcceptView(discord.ui.View):
 def __init__(self,bot,gid,uid,score):super().__init__(timeout=600);self.bot=bot;self.gid=gid;self.uid=uid;self.score=score
 @discord.ui.button(label='Accept Terms & Verify',emoji='✅',style=discord.ButtonStyle.success)
 async def accept_btn(self,i,b):
  if i.user.id!=self.uid:return await i.response.send_message('This verification session belongs to another member.',ephemeral=True)
  db=self.bot.db;g=i.guild
  if not g or g.id!=self.gid or not isinstance(i.user,discord.Member) or i.user.id!=self.uid:return await i.response.send_message('Verification session is no longer valid for this server/member.',ephemeral=True)
  s=db.guild(self.gid);vr=role_by_setting(g,s,'verified_role_id');gr=role_by_setting(g,s,'member_role_id');ur=role_by_setting(g,s,'unverified_role_id')
  if not vr:return await i.response.send_message('⚠️ Verified role is not configured. Ask an administrator to configure it before accepting.',ephemeral=True)
  try:
   await i.user.add_roles(vr,reason='420Vault Terms accepted')
   if gr and gr not in i.user.roles: await i.user.add_roles(gr,reason='420Vault member verified')
   if ur and ur in i.user.roles:await i.user.remove_roles(ur,reason='420Vault Terms accepted')
  except (discord.Forbidden,discord.HTTPException):return await i.response.send_message('⚠️ You passed, but I cannot update roles. Acceptance was NOT saved. An admin must place the bot role above the verification roles.',ephemeral=True)
  db.execute('INSERT INTO tos_acceptance(guild_id,user_id,tos_version,quiz_score) VALUES(?,?,?,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET tos_version=excluded.tos_version,accepted_at=CURRENT_TIMESTAMP,quiz_score=excluded.quiz_score',(self.gid,self.uid,TOS_VERSION,self.score));db.execute('INSERT INTO tos_attempts(guild_id,user_id,failed_sessions,last_attempt_at,last_result) VALUES(?,?,0,CURRENT_TIMESTAMP,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET failed_sessions=0,last_attempt_at=CURRENT_TIMESTAMP,last_result=excluded.last_result',(self.gid,self.uid,'accepted'))
  db.audit(self.gid,self.uid,'tos_accepted',f'version={TOS_VERSION} score={self.score}')
  await i.response.edit_message(content='✅ **Verified.** You accepted the current 420Vault Terms. Server access can now be granted according to your roles/license.',view=None)
 @discord.ui.button(label='Decline',style=discord.ButtonStyle.danger)
 async def decline(self,i,b):await fail_session(self.bot,i,self.gid,self.uid,'declined_after_quiz')

async def fail_session(bot,i,gid,uid,result):
 if i.user.id!=uid:return await i.response.send_message('This verification session belongs to another member.',ephemeral=True)
 db=bot.db;db.execute('INSERT INTO tos_attempts(guild_id,user_id,failed_sessions,last_attempt_at,last_result) VALUES(?,?,1,CURRENT_TIMESTAMP,?) ON CONFLICT(guild_id,user_id) DO UPDATE SET failed_sessions=failed_sessions+1,last_attempt_at=CURRENT_TIMESTAMP,last_result=excluded.last_result',(gid,uid,result));r=db.one('SELECT failed_sessions FROM tos_attempts WHERE guild_id=? AND user_id=?',(gid,uid));fails=int(r['failed_sessions']);limit=int(db.guild(gid).get('tos_max_kicks') or 3);db.audit(gid,uid,'tos_failed',f'{result}; failed_sessions={fails}')
 await i.response.edit_message(content=f'❌ Verification not completed. Failed session **{fails}**. You will be removed from the server.',view=None)
 try:
  if fails>limit:await i.guild.ban(i.user,reason=f'420Vault Terms verification exceeded {limit} allowed rejoin failures',delete_message_seconds=0)
  else:await i.user.kick(reason=f'420Vault Terms verification failed ({fails}/{limit} rejoin failures allowed)')
 except discord.Forbidden:pass

async def publish_tos(bot,guild,channel):
 e=discord.Embed(title='📜 420Vault Terms & Verification',description='Reading and accepting the current Terms is required before using protected server features or 420Vault. Click below to read the Terms and complete the randomized knowledge check.',color=discord.Color.dark_green());e.add_field(name='Verification',value='Read → randomized comprehension check → explicit acceptance → Verified role',inline=False);e.set_footer(text=f'Terms version {TOS_VERSION}')

 s=bot.db.guild(guild.id);mid=s.get('tos_message_id')
 if mid:
  try:
   msg=await channel.fetch_message(int(mid));await msg.edit(embed=e,view=TosStartView(bot));return msg
  except (discord.NotFound,discord.Forbidden,discord.HTTPException):pass
 msg=await channel.send(embed=e,view=TosStartView(bot));bot.db.set_guild(guild.id,tos_message_id=msg.id);return msg

class AccessRoleSelect(discord.ui.RoleSelect):
 def __init__(self,bot,gid,key,label,row):super().__init__(placeholder=label,min_values=1,max_values=1,row=row);self.bot=bot;self.gid=gid;self.key=key
 async def callback(self,i):
  if not i.user.guild_permissions.administrator:return await i.response.send_message('Server Administrator permission is required.',ephemeral=True)
  self.bot.db.set_guild(self.gid,**{self.key:self.values[0].id});await i.response.send_message(f'✅ {self.placeholder}: {self.values[0].mention}',ephemeral=True)
class AccessRoleSetup(discord.ui.View):
 def __init__(self,bot,gid):
  super().__init__(timeout=900)
  self.add_item(AccessRoleSelect(bot,gid,'verified_role_id','TOS Accepted role (passed Terms)',0))
  self.add_item(AccessRoleSelect(bot,gid,'member_role_id','Verified member role',1))
  self.add_item(AccessRoleSelect(bot,gid,'unverified_role_id','Unverified / onboarding role',2))
  self.add_item(AccessRoleSelect(bot,gid,'subscribed_role_id','Paid Member role (subscription)',3))
  self.add_item(AccessRoleSelect(bot,gid,'beta_role_id','Beta Tester role (free user access)',4))
  self.add_item(AccessRoleSelect(bot,gid,'overseer_role_id','Optional custom bot-admin role',4))
class TosChannelSelect(discord.ui.ChannelSelect):
 def __init__(self,bot,gid):super().__init__(placeholder='Terms / verification channel',channel_types=[discord.ChannelType.text],min_values=1,max_values=1);self.bot=bot;self.gid=gid
 async def callback(self,i):
  if not i.user.guild_permissions.administrator:return await i.response.send_message('Server Administrator permission is required.',ephemeral=True)
  ch=self.values[0];self.bot.db.set_guild(self.gid,tos_channel_id=ch.id);await i.response.send_message(f'✅ Terms channel set to {ch.mention}.',ephemeral=True)
class TosChannelSetup(discord.ui.View):
 def __init__(self,bot,gid):super().__init__(timeout=900);self.add_item(TosChannelSelect(bot,gid))
