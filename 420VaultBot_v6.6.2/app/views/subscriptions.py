from __future__ import annotations
import discord
from app.services.payments import PaymentError
from app.views.payment_tickets import create_payment_ticket
class SubscribeView(discord.ui.View):
 def __init__(self,bot,gid,uid):
  super().__init__(timeout=600);self.bot=bot;self.gid=gid;self.uid=uid;bot.db.seed_plans(gid)
  plans=bot.db.all('SELECT * FROM subscription_plans WHERE guild_id=? AND enabled=1 ORDER BY price_cents',(gid,))
  opts=[discord.SelectOption(label=p['name'],description=f"${p['price_cents']/100:.2f} • {'Lifetime' if p['lifetime'] else str(p['duration_days'])+' days'}",value=str(p['id'])) for p in plans[:25]]
  sel=discord.ui.Select(placeholder='Choose a 420Vault plan',options=opts);sel.callback=self.choose;self.add_item(sel)
 async def interaction_check(self,i):
  if i.user.id==self.uid:return True
  await i.response.send_message('This subscription menu belongs to another user.',ephemeral=True);return False
 async def choose(self,i):
  pid=int(i.data['values'][0]);p=self.bot.db.one('SELECT * FROM subscription_plans WHERE id=?',(pid,));await i.response.edit_message(embed=self.embed(p),view=PayView(self.bot,self.gid,self.uid,pid))
 def embed(self,p):
  e=discord.Embed(title=f'💳 {p["name"]}',description=p['description'],color=discord.Color.green());e.add_field(name='Price',value=f'{p["price_cents"]/100:.2f} {p["currency"]}');e.add_field(name='Duration',value='Lifetime' if p['lifetime'] else f'{p["duration_days"]} days');e.add_field(name='Grace',value=f'{p["grace_days"]} days');return e
class PayView(discord.ui.View):
 def __init__(self,bot,gid,uid,pid):super().__init__(timeout=600);self.bot=bot;self.gid=gid;self.uid=uid;self.pid=pid
 async def interaction_check(self,i):return i.user.id==self.uid
 @discord.ui.button(label='Cash App (Manual)',emoji='💵',style=discord.ButtonStyle.secondary)
 async def cash(self,i,b):
  s=self.bot.payments.settings(self.gid,'cashapp');p=self.bot.db.one('SELECT * FROM subscription_plans WHERE id=?',(self.pid,))
  if not s.get('enabled'):return await i.response.send_message('Cash App is not enabled.',ephemeral=True)
  tid=self.bot.db.execute("INSERT INTO transactions(guild_id,user_id,plan_id,provider,amount_cents,currency,status) VALUES(?,?,?,'cashapp',?,?,'pending_manual')",(self.gid,self.uid,self.pid,p['price_cents'],p['currency']))
  await i.response.defer(ephemeral=True,thinking=True)
  try:ch=await create_payment_ticket(self.bot,i.guild,self.uid,tid,p)
  except Exception as ex:return await i.followup.send(f'❌ Payment request created, but ticket creation failed: `{type(ex).__name__}: {ex}`',ephemeral=True)
  await i.followup.send(f'💵 Send **${p["price_cents"]/100:.2f} {p["currency"]}** to **{s.get("cashtag","Not configured")}**.\nReference: `420-{tid}`\n{s.get("instructions","")}\nYour private approval ticket is {ch.mention}. Upload proof there. Access is not granted until an administrator approves it.',ephemeral=True)
 @discord.ui.button(label='Credit / Debit Card',emoji='💳',style=discord.ButtonStyle.primary)
 async def stripe(self,i,b):
  if not self.bot.payments.settings(self.gid,'stripe').get('enabled'):return await i.response.send_message('Stripe is not enabled.',ephemeral=True)
  p=self.bot.db.one('SELECT * FROM subscription_plans WHERE id=?',(self.pid,))
  try:url,tx=await self.bot.payments.stripe_checkout(self.gid,self.uid,p)
  except PaymentError as e:return await i.response.send_message(f'❌ {e}',ephemeral=True)
  self.bot.db.execute("INSERT OR IGNORE INTO transactions(guild_id,user_id,plan_id,provider,provider_transaction_id,amount_cents,currency,status) VALUES(?,?,?,'stripe',?,?,?,'checkout_created')",(self.gid,self.uid,self.pid,tx,p['price_cents'],p['currency']));await i.response.send_message(f'🔒 **Secure card checkout**\nYour card number, expiration date, and CVV are entered on Stripe hosted checkout and are never sent to or stored by 420Vault.\n\nContinue here:\n{url}',ephemeral=True)
 @discord.ui.button(label='PayPal',emoji='🅿️',style=discord.ButtonStyle.primary)
 async def paypal(self,i,b):
  if not self.bot.payments.settings(self.gid,'paypal').get('enabled'):return await i.response.send_message('PayPal is not enabled.',ephemeral=True)
  p=self.bot.db.one('SELECT * FROM subscription_plans WHERE id=?',(self.pid,))
  try:url,tx=await self.bot.payments.paypal_checkout(self.gid,self.uid,p)
  except PaymentError as e:return await i.response.send_message(f'❌ {e}',ephemeral=True)
  self.bot.db.execute("INSERT OR IGNORE INTO transactions(guild_id,user_id,plan_id,provider,provider_transaction_id,amount_cents,currency,status) VALUES(?,?,?,'paypal',?,?,?,'checkout_created')",(self.gid,self.uid,self.pid,tx,p['price_cents'],p['currency']));await i.response.send_message(f'Approve the subscription here:\n{url}',ephemeral=True)
