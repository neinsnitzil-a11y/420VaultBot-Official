from __future__ import annotations
import logging,socket,hashlib,asyncio
from pathlib import Path
from datetime import datetime,timezone
import discord
from discord.ext import commands,tasks
from app.core.config import TOKEN,APP_DB
from app.core.database import Database
from app.services.search import SearchService
from app.services.link_search import LinkSearchService
from app.services.link_preview import LinkPreviewService
from app.services.subscriptions import SubscriptionService
from app.services.payments import PaymentService
from app.services.webhooks import WebhookServer
from app.views.license import LicenseView,DMLicenseView,license_embed
from app.views.payment_tickets import PaymentTicketView,create_payment_ticket
from app.services.access import check_access
from app.views.tos import TosStartView,accepted,role_by_setting
from app.views.support_tickets import SupportTicketPanel,SupportTicketActions,ticket_panel_embed
from app.services.server_bootstrap import ensure_server_bootstrap
from app.services.google_drive import GoogleDriveService
from app.core.licensing import license_signature
from app.services.heartbeat_watchdog import HeartbeatWatchdog

LOG_FORMAT='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
class VaultBot(commands.Bot):
 def __init__(self):
  intents=discord.Intents.default();intents.guilds=True;intents.members=True;intents.message_content=True
  super().__init__(command_prefix='420_',intents=intents,help_command=None,case_insensitive=True)
  self.db=Database(APP_DB);self.search=SearchService(self.db);self.link_search=LinkSearchService(Path(__file__).resolve().parents[1],self.db);self.link_preview=LinkPreviewService();self.subscriptions=SubscriptionService(self);self.payments=PaymentService(self);self.webhooks=WebhookServer(self);self._ready_once=False;self._migrate_entitlements()
  self.google_drive=GoogleDriveService(self.db)
  self.heartbeat_watchdog=HeartbeatWatchdog(self,Path(__file__).resolve().parents[1]/'data'/'heartbeat.json')
  self.heartbeat_watchdog.start()

 def _migrate_entitlements(self):
  # Preserve pre-v3.4 licenses by converting them into explicit entitlements and server-side HMAC records.
  for r in self.db.all("SELECT * FROM licenses WHERE entitlement_id IS NULL OR signature_hmac IS NULL"):
   uid=r['assigned_user_id'] or r['user_id']
   if not uid:continue
   sub=self.db.one('SELECT id FROM subscriptions WHERE license_code=? ORDER BY id DESC LIMIT 1',(r['code'],))
   eid=r['entitlement_id']
   if not eid:eid=self.db.execute("INSERT INTO entitlements(guild_id,user_id,source,status,starts_at,expires_at,subscription_id) VALUES(?,?,?,? ,CURRENT_TIMESTAMP,?,?)",(r['guild_id'],uid,'subscription' if sub else 'legacy_admin_grant','active' if r['status']=='active' else r['status'],r['expires_at'],sub['id'] if sub else None))
   try:sig=license_signature(r['code'])
   except Exception:sig=None
   self.db.execute('UPDATE licenses SET entitlement_id=?,signature_hmac=COALESCE(signature_hmac,?) WHERE code=?',(eid,sig,r['code']))
 async def setup_hook(self):
  await self.load_extension('app.cogs.legacy_commands');self.add_view(LicenseView(self));self.add_view(TosStartView(self));self.add_view(SupportTicketPanel(self));self.add_view(SupportTicketActions(self))
  for r in self.db.all("SELECT code,guild_id FROM licenses WHERE status='active' AND assigned_user_id IS NOT NULL"):
   try:self.add_view(DMLicenseView(self,int(r['guild_id']),r['code']))
   except Exception:pass
  for r in self.db.all("SELECT transaction_id,ticket_type FROM payment_tickets WHERE status='open'"):
   try:self.add_view(PaymentTicketView(self,int(r['transaction_id']),r['ticket_type']))
   except Exception:pass
  self.tree.clear_commands(guild=None);await self.tree.sync();await self.webhooks.start();self.entitlement_worker.start();self.audit_log_worker.start()
 async def close(self):
  self.heartbeat_watchdog.stop()
  if self.entitlement_worker.is_running():self.entitlement_worker.cancel()
  if self.audit_log_worker.is_running():self.audit_log_worker.cancel()
  await self.webhooks.stop();await super().close()
 async def deliver_license(self,gid,uid,code,plan=None,expires=None):
  try:user=self.get_user(uid) or await self.fetch_user(uid)
  except Exception:return False
  e=discord.Embed(title='🔐 Your 420Vault License',color=discord.Color.green());e.add_field(name='License',value=f'`{code}`',inline=False);e.add_field(name='Plan',value=(plan['name'] if plan else 'Manual License'));e.add_field(name='Expires',value=(str(expires) if expires else 'Never'));e.add_field(name='Status',value='Awaiting activation');e.set_footer(text='420Vault never asks you to send card details through Discord.')
  try:await user.send(content='Your license is ready. Click **Activate License** below — no activation command is required.',embed=e,view=DMLicenseView(self,gid,code));return True
  except (discord.Forbidden,discord.HTTPException):return False
 async def ensure_license_panel(self,guild_id:int,force=False):
  guild=self.get_guild(guild_id);s=self.db.guild(guild_id)
  if not guild or not s.get('license_channel_id'):return False
  ch=guild.get_channel(s['license_channel_id']);
  if not isinstance(ch,discord.TextChannel):return False
  old=[]
  try:
   async for m in ch.history(limit=100):
    if m.author==self.user and m.embeds and m.embeds[0].title=='🔐 420VaultBot Locked':old.append(m)
  except discord.Forbidden:return False
  if old and not force:return True
  if force:
   for m in old:
    try:await m.delete()
    except:pass
  try:
   m=await ch.send(embed=license_embed(),view=LicenseView(self));
   try:await m.pin(reason='420Vault license activation panel')
   except:pass
   return True
  except:return False
 async def log_event(self,guild_id,kind,message,level='INFO'):
  log=getattr(logging,level.lower(),logging.info);log('[%s][guild=%s] %s',kind,guild_id,message)
  try:
   g=self.get_guild(int(guild_id));st=self.db.guild(int(guild_id));ch=g.get_channel(st.get('log_channel_id')) if g and st.get('log_channel_id') else None
   if ch:await ch.send(f'`{level}` **{kind}** • {str(message)[:1750]}')
  except (discord.Forbidden,discord.HTTPException):pass
 async def ensure_ticket_panel(self,guild_id:int):
  g=self.get_guild(guild_id);st=self.db.guild(guild_id);ch=g.get_channel(st.get('ticket_channel_id')) if g and st.get('ticket_channel_id') else None
  if not isinstance(ch,discord.TextChannel):return False
  mid=st.get('ticket_message_id')
  if mid:
   try:m=await ch.fetch_message(mid);await m.edit(embed=ticket_panel_embed(),view=SupportTicketPanel(self));return True
   except (discord.NotFound,discord.Forbidden,discord.HTTPException):pass
  try:
   m=await ch.send(embed=ticket_panel_embed(),view=SupportTicketPanel(self));self.db.set_guild(guild_id,ticket_message_id=m.id)
   try:await m.pin(reason='420Vault support ticket panel')
   except (discord.Forbidden,discord.HTTPException):pass
   return True
  except (discord.Forbidden,discord.HTTPException):return False
 async def _payment_tx(self,provider,event_id,gid,uid,plan_id=None,sub_id=None,provider_tx=None,amount=None,currency='USD',status='event'):
  existing=self.db.one('SELECT id FROM transactions WHERE provider=? AND provider_event_id=?',(provider,event_id))
  if existing:return int(existing['id'])
  return self.db.execute('INSERT INTO transactions(guild_id,user_id,plan_id,subscription_id,provider,provider_transaction_id,provider_event_id,amount_cents,currency,status) VALUES(?,?,?,?,?,?,?,?,?,?)',(gid,uid,plan_id,sub_id,provider,provider_tx,event_id,amount,currency,status))
 async def _review_ticket(self,provider,event_id,gid,uid,sub_id,event_type,details,provider_tx=None,status='review'):
  s=self.db.one('SELECT plan_id FROM subscriptions WHERE id=?',(sub_id,)) if sub_id else None
  tx=await self._payment_tx(provider,event_id,gid,uid,s['plan_id'] if s else None,sub_id,provider_tx,None,'USD',status)
  g=self.get_guild(gid)
  if g:await create_payment_ticket(self,g,uid,tx,None,'provider_review',f'⚠️ {provider.title()} Payment Review',f'Event: **{event_type}**\n{details}',provider,event_id)
  return tx
 async def create_system_payment_ticket(self,provider,ev,error):
  et=ev.get('type') or ev.get('event_type','unknown');obj=(ev.get('data',{}).get('object') if provider=='stripe' else ev.get('resource',{})) or {};subid=obj.get('subscription') or obj.get('billing_agreement_id') or obj.get('id')
  r=self.db.one('SELECT id,guild_id,user_id FROM subscriptions WHERE provider=? AND provider_subscription_id=?',(provider,subid)) if subid else None
  if r:await self._review_ticket(provider,ev.get('id','unknown'),r['guild_id'],r['user_id'],r['id'],et,'Webhook processing error: '+type(error).__name__,subid,'processing_error')
 async def _stripe_transaction_context(self,obj):
  """Resolve charge/dispute objects back to our original paid transaction/subscription."""
  payment_intent=obj.get('payment_intent')
  charge_id=obj.get('charge') if obj.get('object')=='dispute' else obj.get('id')
  if not payment_intent and charge_id:
   try:
    import stripe
    charge=await asyncio.to_thread(stripe.Charge.retrieve,charge_id)
    payment_intent=charge.get('payment_intent')
   except Exception:
    logging.exception('Unable to resolve Stripe charge %s for dispute/refund',charge_id)
  tx=self.db.one("SELECT * FROM transactions WHERE provider='stripe' AND provider_transaction_id=? ORDER BY id DESC LIMIT 1",(payment_intent,)) if payment_intent else None
  if not tx and charge_id: tx=self.db.one("SELECT * FROM transactions WHERE provider='stripe' AND provider_transaction_id=? ORDER BY id DESC LIMIT 1",(charge_id,))
  return tx
 async def _paypal_transaction_context(self,obj):
  ids=[]
  for x in obj.get('disputed_transactions',[]) or []:
   info=x.get('seller_transaction_id') or x.get('buyer_transaction_id')
   if info: ids.append(info)
  for k in ('sale_id','capture_id','parent_payment','id'):
   if obj.get(k): ids.append(obj.get(k))
  for ident in ids:
   tx=self.db.one("SELECT * FROM transactions WHERE provider='paypal' AND provider_transaction_id=? ORDER BY id DESC LIMIT 1",(ident,))
   if tx:return tx
  return None
 def _mark_payment_review_state(self,provider,sub_id,state):
  # Keep the original purchase record and reflect its post-payment lifecycle.
  if sub_id:self.db.execute("UPDATE transactions SET status=?,updated_at=CURRENT_TIMESTAMP WHERE provider=? AND subscription_id=? AND status='paid'",(state,provider,sub_id))
 async def handle_payment_event(self,provider,ev):
  et=ev.get('type') or ev.get('event_type','');eid=ev.get('id','');obj=(ev.get('data',{}).get('object') if provider=='stripe' else ev.get('resource',{})) or {}
  if provider=='stripe':
   if et=='checkout.session.completed':
    md=obj.get('metadata',{});ref=str(obj.get('client_reference_id','')).split(':');gid=int(md.get('guild_id') or ref[0]);uid=int(md.get('user_id') or ref[1]);pid=int(md.get('plan_id') or ref[2]);sub=obj.get('subscription');customer=obj.get('customer')
    if obj.get('mode')=='subscription':
     # Checkout completion only links the provider subscription. Paid access waits for invoice.paid/payment_succeeded.
     sid=self.subscriptions.create_pending(gid,uid,pid,'stripe',sub,customer,True);await self._payment_tx('stripe',eid,gid,uid,pid,sid,obj.get('id'),obj.get('amount_total'),str(obj.get('currency','USD')).upper(),'checkout_completed');return
    if obj.get('payment_status')!='paid':return
    key=obj.get('id');sid=self.subscriptions.create_pending(gid,uid,pid,'stripe',key,customer,False);c,p,exp,created=self.subscriptions.fulfill_pending(sid);await self._payment_tx('stripe',eid,gid,uid,pid,sid,obj.get('payment_intent') or obj.get('id'),obj.get('amount_total'),str(obj.get('currency','USD')).upper(),'paid')
    if created:await self.deliver_license(gid,uid,c,p,exp)
    return
   subid=obj.get('subscription') or (obj.get('id') if et.startswith('customer.subscription.') else None);r=self.db.one("SELECT s.*,p.duration_days,p.lifetime,p.grace_days FROM subscriptions s JOIN subscription_plans p ON p.id=s.plan_id WHERE s.provider='stripe' AND s.provider_subscription_id=?",(subid,)) if subid else None
   if not r and et in ('charge.refunded','charge.dispute.created','charge.dispute.updated','charge.dispute.closed'):
    tx=await self._stripe_transaction_context(obj)
    if tx and tx['subscription_id']:
     r=self.db.one("SELECT s.*,p.duration_days,p.lifetime,p.grace_days FROM subscriptions s JOIN subscription_plans p ON p.id=s.plan_id WHERE s.id=?",(tx['subscription_id'],));subid=r['provider_subscription_id'] if r else None
   if not r:return
   if et in ('invoice.payment_succeeded','invoice.paid'):
    await self._payment_tx('stripe',eid,r['guild_id'],r['user_id'],r['plan_id'],r['id'],obj.get('payment_intent') or obj.get('id'),obj.get('amount_paid'),str(obj.get('currency','USD')).upper(),'paid')
    period_end=None
    try:
     ends=[ln.get('period',{}).get('end') for ln in obj.get('lines',{}).get('data',[]) if ln.get('period',{}).get('end')]
     if ends:period_end=datetime.fromtimestamp(max(ends),timezone.utc).isoformat()
    except Exception:
     logging.exception('Failed to parse Stripe invoice billing period for event %s',eid)
    if r['status']=='pending' or not r['license_code']:
     c,p,exp,created=self.subscriptions.fulfill_pending(r['id'],period_end)
     if created:await self.deliver_license(r['guild_id'],r['user_id'],c,p,exp)
    elif not r['lifetime']:
     exp=period_end or r['expires_at'];self.db.execute("UPDATE subscriptions SET status='active',expires_at=?,grace_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(exp,r['id']));self.db.execute("UPDATE licenses SET status='active',expires_at=? WHERE code=?",(exp,r['license_code']));self.db.execute("UPDATE entitlements SET status='active',expires_at=?,grace_until=NULL WHERE subscription_id=?",(exp,r['id']))
   elif et=='invoice.payment_failed':
    from datetime import timedelta
    grace=self.subscriptions.mark_past_due(r['id']);await self._review_ticket('stripe',eid,r['guild_id'],r['user_id'],r['id'],et,f'Renewal failed. Access remains in grace until `{grace.isoformat()}`.',obj.get('id'),'failed')
   elif et=='charge.refunded':
    self._mark_payment_review_state('stripe',r['id'],'refunded');await self._review_ticket('stripe',eid,r['guild_id'],r['user_id'],r['id'],et,'Refund received. Access requires administrator review.',obj.get('id'),'refunded')
   elif et in ('charge.dispute.created','charge.dispute.updated'):
    self._mark_payment_review_state('stripe',r['id'],'disputed');await self._review_ticket('stripe',eid,r['guild_id'],r['user_id'],r['id'],et,'Charge dispute received. Access requires administrator review.',obj.get('id'),'disputed')
   elif et=='charge.dispute.closed':
    outcome=obj.get('status') or 'closed';await self._review_ticket('stripe',eid,r['guild_id'],r['user_id'],r['id'],et,f'Dispute closed with provider status: {outcome}. Administrator review required.',obj.get('id'),'dispute_closed')
   elif et=='customer.subscription.deleted':
    self.db.execute("UPDATE subscriptions SET status='expired',updated_at=CURRENT_TIMESTAMP WHERE id=?",(r['id'],));self.db.execute("UPDATE entitlements SET status='expired' WHERE subscription_id=?",(r['id'],));self.db.execute("UPDATE licenses SET status='expired' WHERE code=?",(r['license_code'],));await self._review_ticket('stripe',eid,r['guild_id'],r['user_id'],r['id'],et,'Provider subscription cancelled; access expired.',subid,'cancelled')
  else:
   if et=='BILLING.SUBSCRIPTION.ACTIVATED':
    custom=str(obj.get('custom_id','')).split(':')
    if len(custom)==3:
     gid,uid,pid=map(int,custom);subid=obj.get('id');existing=self.db.one("SELECT id FROM subscriptions WHERE provider='paypal' AND provider_subscription_id=?",(subid,))
     if not existing:
      sid=self.subscriptions.create_pending(gid,uid,pid,'paypal',subid,None,True);await self._payment_tx('paypal',eid,gid,uid,pid,sid,subid,None,'USD','subscription_activated')
    return
   subid=obj.get('billing_agreement_id') or obj.get('id');r=self.db.one("SELECT s.*,p.duration_days,p.lifetime,p.grace_days FROM subscriptions s JOIN subscription_plans p ON p.id=s.plan_id WHERE s.provider='paypal' AND s.provider_subscription_id=?",(subid,)) if subid else None
   if not r:return
   if et in ('PAYMENT.SALE.COMPLETED','BILLING.SUBSCRIPTION.PAYMENT.SUCCEEDED'):
    amt=obj.get('amount',{});cents=None
    try:cents=round(float(amt.get('total') or amt.get('value'))*100)
    except (TypeError,ValueError):
     logging.warning('PayPal event %s had an invalid amount',eid)
    await self._payment_tx('paypal',eid,r['guild_id'],r['user_id'],r['plan_id'],r['id'],obj.get('id'),cents,(amt.get('currency') or amt.get('currency_code') or 'USD'),'paid')
    period_end=await self.payments.paypal_billing_period_end(subid) if not r['lifetime'] else None
    if r['status']=='pending' or not r['license_code']:
     c,p,exp,created=self.subscriptions.fulfill_pending(r['id'],period_end)
     if created:await self.deliver_license(r['guild_id'],r['user_id'],c,p,exp)
    elif not r['lifetime']:
     self.subscriptions.renew(r['id'],period_end)
   elif et in ('BILLING.SUBSCRIPTION.PAYMENT.FAILED','BILLING.SUBSCRIPTION.SUSPENDED'):
    grace=self.subscriptions.mark_past_due(r['id']);await self._review_ticket('paypal',eid,r['guild_id'],r['user_id'],r['id'],et,f'Payment failed/suspended. Grace until `{grace.isoformat()}`.',subid,'failed')
   elif et in ('PAYMENT.SALE.REFUNDED','PAYMENT.SALE.REVERSED','CUSTOMER.DISPUTE.CREATED','CUSTOMER.DISPUTE.UPDATED'):
    await self._review_ticket('paypal',eid,r['guild_id'],r['user_id'],r['id'],et,'Refund, reversal, or dispute requires administrator review.',obj.get('id'),'review')
   elif et in ('BILLING.SUBSCRIPTION.CANCELLED','BILLING.SUBSCRIPTION.EXPIRED'):
    self.db.execute("UPDATE subscriptions SET status='expired',updated_at=CURRENT_TIMESTAMP WHERE id=?",(r['id'],));self.db.execute("UPDATE entitlements SET status='expired' WHERE subscription_id=?",(r['id'],));self.db.execute("UPDATE licenses SET status='expired' WHERE code=?",(r['license_code'],));await self._review_ticket('paypal',eid,r['guild_id'],r['user_id'],r['id'],et,'Provider subscription ended; access expired.',subid,'cancelled')
 async def sync_member_access_roles(self,gid,uid):
  g=self.get_guild(int(gid));s=self.db.guild(int(gid));m=g.get_member(int(uid)) if g else None
  if not m:return
  subscribed=role_by_setting(g,s,'subscribed_role_id');beta=role_by_setting(g,s,'beta_role_id');overseer=role_by_setting(g,s,'overseer_role_id');verified=role_by_setting(g,s,'verified_role_id');general_verified=role_by_setting(g,s,'member_role_id');unverified=role_by_setting(g,s,'unverified_role_id')
  admin_bypass=check_access(self,g,m,require_admin=True).allowed
  is_verified=admin_bypass or (not s.get('tos_enabled',1)) or accepted(self.db,g.id,m.id) or bool(verified and verified in m.roles)
  state=check_access(self,g,m);active=self.subscriptions.active_for(g.id,m.id);paid=bool(active and state.allowed)
  try:
   if is_verified:
    if verified and verified not in m.roles:await m.add_roles(verified,reason='420Vault Terms verified/current or gate disabled')
    if general_verified and general_verified not in m.roles:await m.add_roles(general_verified,reason='420Vault member verified')
    if unverified and unverified in m.roles:await m.remove_roles(unverified,reason='420Vault Terms verified/current or gate disabled')
   else:
    if verified and verified in m.roles:await m.remove_roles(verified,reason='420Vault Terms version re-verification required')
    if general_verified and general_verified in m.roles:await m.remove_roles(general_verified,reason='420Vault Terms version re-verification required')
    if unverified and unverified not in m.roles:await m.add_roles(unverified,reason='420Vault Terms verification required')
   if subscribed:
    if paid and subscribed not in m.roles:await m.add_roles(subscribed,reason='420Vault paid subscription active')
    if not paid and subscribed in m.roles:await m.remove_roles(subscribed,reason='420Vault paid subscription inactive')
  except (discord.Forbidden,discord.HTTPException):pass
 async def on_guild_join(self,guild):
  self.db.seed_plans(guild.id);await ensure_server_bootstrap(self,guild)
 async def on_member_join(self,member):
  # v4 onboarding: admins/Overseers bypass TOS; normal members are placed in
  # Unverified and directed to the configured #terms onboarding destination.
  await self.sync_member_access_roles(member.guild.id,member.id)
  s=self.db.guild(member.guild.id)
  if s.get('tos_enabled',1) and not check_access(self,member.guild,member,require_admin=True).allowed and not accepted(self.db,member.guild.id,member.id):
   ch=member.guild.get_channel(s.get('tos_channel_id')) if s.get('tos_channel_id') else None
   if not isinstance(ch,discord.TextChannel):
    from app.services.server_bootstrap import ensure_server_bootstrap
    found=await ensure_server_bootstrap(self,member.guild);ch=found.get('terms')
   if isinstance(ch,discord.TextChannel):
    url=f'https://discord.com/channels/{member.guild.id}/{ch.id}'
    view=discord.ui.View(timeout=300);view.add_item(discord.ui.Button(label='Open Terms & Verify',emoji='📜',style=discord.ButtonStyle.link,url=url))
    try:await member.send(f'👋 **Welcome to {member.guild.name}.** Before using the server, complete the 420Vault onboarding in {ch.mention}.\n\nRead the Terms, complete the verification check, and accept them to receive the **Verified** role.',view=view)
    except (discord.Forbidden,discord.HTTPException):pass
   await self.log_event(member.guild.id,'ONBOARDING',f'{member} ({member.id}) joined and was routed to Terms verification.')

 @tasks.loop(seconds=15)
 async def audit_log_worker(self):
  if not hasattr(self,'_audit_seen'):
   self._audit_seen={}
   for g in self.guilds:
    row=await asyncio.to_thread(self.db.one,'SELECT COALESCE(MAX(id),0) n FROM audit_log WHERE guild_id=?',(g.id,))
    self._audit_seen[g.id]=int((row or {'n':0})['n'])
   return
  for g in self.guilds:
   last=self._audit_seen.get(g.id,0);rows=await asyncio.to_thread(self.db.all,'SELECT * FROM audit_log WHERE guild_id=? AND id>? ORDER BY id LIMIT 50',(g.id,last))
   for r in rows:
    await self.log_event(g.id,'AUDIT',f'{r["action"]} • user={r["user_id"] or "system"} • {r["details"] or ""}')
    self._audit_seen[g.id]=r['id']
 @audit_log_worker.before_loop
 async def before_audit_logs(self):await self.wait_until_ready()
 @tasks.loop(minutes=15)
 async def entitlement_worker(self):
  for s in await asyncio.to_thread(self.subscriptions.expire_due):
   g=self.get_guild(s['guild_id']);settings=self.db.guild(s['guild_id']);member=g.get_member(s['user_id']) if g else None;role=g.get_role(settings.get('member_role_id')) if g and settings.get('member_role_id') else None;subrole=role_by_setting(g,settings,'subscribed_role_id') if g else None
   if member:
    try:
     if role:await member.remove_roles(role,reason='420Vault subscription expired')
     if subrole:await member.remove_roles(subrole,reason='420Vault subscription expired')
    except:pass
   try:u=self.get_user(s['user_id']) or await self.fetch_user(s['user_id']);await u.send('⚠️ Your 420Vault subscription/grace period has ended. Your subscription license has been automatically revoked. Use `420_subscribe` in the server to purchase access again.')
   except:pass
  # Reconcile paid-role state even if a provider event happened while Discord was unavailable.
  for r in await asyncio.to_thread(self.db.all,"SELECT DISTINCT guild_id,user_id FROM subscriptions WHERE status IN ('active','past_due','expired')"):
   await self.sync_member_access_roles(r['guild_id'],r['user_id'])
 @entitlement_worker.before_loop
 async def before_entitlements(self):await self.wait_until_ready()
 async def on_command_completion(self,ctx):
  if ctx.guild:await self.log_event(ctx.guild.id,'COMMAND',f'{ctx.author} ({ctx.author.id}) ran 420_{ctx.command.qualified_name} in #{getattr(ctx.channel,"name","unknown")}')
 async def on_command_error(self,ctx,error):
  if ctx.guild:await self.log_event(ctx.guild.id,'COMMAND_ERROR',f'{ctx.author} ({ctx.author.id}) • {type(error).__name__}: {error}',level='ERROR')
  if isinstance(error,commands.CommandNotFound):return
  try:await ctx.send(f'❌ {type(error).__name__}: {error}')
  except (discord.Forbidden,discord.HTTPException):pass
 async def on_ready(self):
  from app.version import VERSION
  logging.getLogger(__name__).info('420VaultBot v%s ready as %s',VERSION,self.user)
  if not self._ready_once:
   self._ready_once=True
   for g in self.guilds:
    self.db.seed_plans(g.id);await ensure_server_bootstrap(self,g)
    # Auto-load every shipped list/list-part file into the unified managed-link index once per guild.
    try:
     from app.services.link_library import LinkLibrary
     await asyncio.to_thread(LinkLibrary(self.db).import_bundled_lists,g.id)
    except Exception as exc:
     logging.getLogger(__name__).warning('Bundled link-list import failed for guild %s: %s',g.id,exc)
    # Register a persistent admin dispatcher for panels created by 420_admin.
    # Stable custom_ids let newly-created panels survive process reconnects/restarts.
    try:
     from app.views.admin import AdminView
     self.add_view(AdminView(self,g.id))
    except Exception as exc:
     logging.getLogger(__name__).warning('Could not register persistent admin view for guild %s: %s',g.id,exc)
_instance_socket=None
def _single_instance():
 global _instance_socket
 port=43000+(int(hashlib.sha256(TOKEN.encode()).hexdigest()[:6],16)%1000);sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
 try:sock.bind(('127.0.0.1',port));sock.listen(1)
 except OSError:raise SystemExit('420VaultBot is already running.')
 _instance_socket=sock
def run():
 if not TOKEN:raise SystemExit('DISCORD_TOKEN is missing. Run setup_and_start.py first.')
 _single_instance();logging.basicConfig(level=logging.INFO,format=LOG_FORMAT);VaultBot().run(TOKEN,log_handler=None)


if __name__ == '__main__':
 run()
