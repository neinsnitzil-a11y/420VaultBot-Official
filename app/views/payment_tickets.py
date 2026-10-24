from __future__ import annotations
from datetime import datetime,timedelta,timezone
import discord
from app.core.security import is_admin

class PaymentTicketView(discord.ui.View):
 def __init__(self,bot,txid:int,ticket_type='manual_approval'):
  super().__init__(timeout=None);self.bot=bot;self.txid=int(txid);self.ticket_type=ticket_type
  acts=[('Approve','✅',discord.ButtonStyle.green,'approve'),('Reject','❌',discord.ButtonStyle.red,'reject'),('Request Info','💬',discord.ButtonStyle.secondary,'info'),('Close','🔒',discord.ButtonStyle.secondary,'close')] if ticket_type=='manual_approval' else [('Recheck Provider','🔄',discord.ButtonStyle.primary,'recheck'),('Notify Customer','📨',discord.ButtonStyle.secondary,'notify'),('Extend Grace 7d','⏳',discord.ButtonStyle.secondary,'grace'),('Revoke Access','🚫',discord.ButtonStyle.red,'revoke'),('Close','🔒',discord.ButtonStyle.secondary,'close')]
  for label,emoji,style,act in acts:
   b=discord.ui.Button(label=label,emoji=emoji,style=style,custom_id=f'420vault:payticket:{self.txid}:{act}');b.callback=lambda i,a=act:self.action(i,a);self.add_item(b)
 async def action(self,i,act):
  t=self.bot.db.one('SELECT * FROM transactions WHERE id=?',(self.txid,));pt=self.bot.db.one('SELECT * FROM payment_tickets WHERE transaction_id=?',(self.txid,))
  if not t:return await i.response.send_message('Transaction no longer exists.',ephemeral=True)
  if not is_admin(i,self.bot.db.guild(t['guild_id'])):return await i.response.send_message('Administrator access required.',ephemeral=True)
  typ=pt['ticket_type'] if pt else self.ticket_type
  if act=='approve' and typ=='manual_approval':
   try:
    sid,c,p,exp,created=self.bot.subscriptions.approve_manual_transaction(self.txid)
   except ValueError as ex:return await i.response.send_message(str(ex),ephemeral=True)
   ok=await self.bot.deliver_license(t['guild_id'],t['user_id'],c,p,exp) if created else True
   self.bot.db.audit(t['guild_id'],i.user.id,'manual_payment_approved',f'transaction={self.txid} created={created}')
   return await i.response.send_message(f'✅ Approved/idempotent. Subscription + entitlement + license are committed atomically. DM: {"sent" if ok else "blocked"}.')
  if act=='reject' and typ=='manual_approval':self.bot.db.execute("UPDATE transactions SET status='rejected',updated_at=CURRENT_TIMESTAMP WHERE id=?",(self.txid,));self.bot.db.execute("UPDATE payment_tickets SET status='rejected' WHERE transaction_id=?",(self.txid,));return await i.response.send_message('❌ Payment rejected. No entitlement/license was created.')
  if act=='info':return await i.response.send_message(f'<@{t["user_id"]}> please provide additional payment information/proof in this ticket.')
  if act=='recheck':
   await i.response.defer(ephemeral=True);status=await self.bot.payments.reconcile_transaction(dict(t));return await i.followup.send(f'Provider status: **{status}**',ephemeral=True)
  if act=='notify':
   try:u=self.bot.get_user(t['user_id']) or await self.bot.fetch_user(t['user_id']);await u.send(f'⚠️ Your 420Vault {t["provider"]} payment needs attention. Please update/check your payment method. Transaction reference: 420-{self.txid}.')
   except Exception:return await i.response.send_message('Discord could not deliver the customer DM.',ephemeral=True)
   return await i.response.send_message('📨 Customer notified.',ephemeral=True)
  if act=='grace':
   s=self.bot.db.one('SELECT * FROM subscriptions WHERE id=?',(t['subscription_id'],)) if t['subscription_id'] else None
   if not s:return await i.response.send_message('No linked subscription.',ephemeral=True)
   g=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat();self.bot.db.execute("UPDATE subscriptions SET status='past_due',grace_until=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(g,s['id']));self.bot.db.execute("UPDATE entitlements SET status='active',grace_until=?,expires_at=? WHERE subscription_id=?",(g,g,s['id']));return await i.response.send_message(f'⏳ Grace extended through `{g}`.',ephemeral=True)
  if act=='revoke':
   if t['subscription_id']:
    self.bot.db.execute("UPDATE subscriptions SET status='expired',updated_at=CURRENT_TIMESTAMP WHERE id=?",(t['subscription_id'],));self.bot.db.execute("UPDATE entitlements SET status='expired' WHERE subscription_id=?",(t['subscription_id'],));self.bot.db.execute("UPDATE licenses SET status='revoked' WHERE entitlement_id IN (SELECT id FROM entitlements WHERE subscription_id=?)",(t['subscription_id'],))
   return await i.response.send_message('🚫 Linked entitlement/license revoked.',ephemeral=True)
  if act=='close':
   self.bot.db.execute("UPDATE payment_tickets SET status='closed' WHERE transaction_id=?",(self.txid,));await i.response.send_message('🔒 Closing ticket…')
   try:await i.channel.delete(reason='420Vault payment review closed')
   except:pass

async def create_payment_ticket(bot,guild,uid,txid,plan=None,ticket_type='manual_approval',title=None,details=None,provider=None,event_id=None):
 existing=bot.db.one('SELECT channel_id FROM payment_tickets WHERE transaction_id=?',(txid,))
 if existing:
  ch=guild.get_channel(existing['channel_id']);
  if ch:return ch
 hub=guild.get_channel(bot.db.guild(guild.id).get('ticket_channel_id')) if bot.db.guild(guild.id).get('ticket_channel_id') else None
 cat=hub.category if isinstance(hub,discord.TextChannel) and hub.category else discord.utils.get(guild.categories,name='420 BOT TICKETS')
 if not cat:cat=await guild.create_category('420 BOT TICKETS',reason='420Vault tickets')
 user=guild.get_member(uid)
 if not user:
  try:user=await guild.fetch_member(uid)
  except Exception:user=None
 settings=bot.db.guild(guild.id);ow={guild.default_role:discord.PermissionOverwrite(view_channel=False),guild.me:discord.PermissionOverwrite(view_channel=True,send_messages=True,manage_channels=True,read_message_history=True)}
 if user:ow[user]=discord.PermissionOverwrite(view_channel=True,send_messages=True,attach_files=True,read_message_history=True)
 if settings.get('admin_role_id'):
  role=guild.get_role(settings['admin_role_id']);
  if role:ow[role]=discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True,manage_messages=True)
 uname=(user.name if user else f'user-{uid}').lower().replace(' ','-')[:30];ch=await guild.create_text_channel(f'payment-{uname}-{txid}',category=cat,overwrites=ow,reason='420Vault payment review')
 bot.db.execute('INSERT OR REPLACE INTO payment_tickets(transaction_id,guild_id,user_id,channel_id,status,ticket_type,provider,provider_event_id) VALUES(?,?,?,?,?,?,?,?)',(txid,guild.id,uid,ch.id,'open',ticket_type,provider,event_id))
 if ticket_type=='manual_approval':
  e=discord.Embed(title=title or f'💵 Payment Approval #{txid}',description=f'Customer: <@{uid}>\nPost payment proof/screenshots in this private ticket. An administrator must approve before access is granted.',color=discord.Color.gold());
  if plan:e.add_field(name='Plan',value=plan['name']);e.add_field(name='Amount',value=f'${plan["price_cents"]/100:.2f} {plan["currency"]}')
  e.add_field(name='Reference',value=f'`420-{txid}`');e.add_field(name='Status',value='🟡 PENDING')
 else:
  e=discord.Embed(title=title or f'⚠️ Payment Review #{txid}',description=f'Customer: <@{uid}>\nProvider: **{provider or "unknown"}**\n{details or "This payment event requires administrator attention."}',color=discord.Color.orange());e.add_field(name='Transaction',value=f'`420-{txid}`');e.add_field(name='Event',value=f'`{event_id or "n/a"}`');e.add_field(name='Status',value='🟠 REVIEW')
 await ch.send(content=f'<@{uid}>' if user else None,embed=e,view=PaymentTicketView(bot,txid,ticket_type));await bot.log_event(guild.id,'PAYMENT_TICKET',f'Opened {ticket_type} ticket for transaction 420-{txid}, user {uid}.');return ch
