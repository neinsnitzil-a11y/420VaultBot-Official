from __future__ import annotations
import secrets
from datetime import datetime
import discord
from app.core.security import is_admin_member

class GrantModal(discord.ui.Modal,title='Generate License'):
 days=discord.ui.TextInput(label='Access days (0 = lifetime)',default='30',max_length=5)
 activations=discord.ui.TextInput(label='Maximum activations',default='1',max_length=3)
 note=discord.ui.TextInput(label='Order / admin note (optional)',required=False,max_length=120)
 def __init__(self,view):super().__init__();self.v=view
 async def on_submit(self,i):
  if not self.v.user_id:return await i.response.send_message('Select a customer first.',ephemeral=True)
  try:days=max(0,int(self.days.value));acts=max(1,int(self.activations.value))
  except ValueError:return await i.response.send_message('Days and activations must be numbers.',ephemeral=True)
  await i.response.defer(ephemeral=True,thinking=True)
  uid=self.v.user_id;order='ORD-'+datetime.utcnow().strftime('%Y%m%d')+'-'+secrets.token_hex(3).upper()
  eid,code,exp=self.v.bot.subscriptions.admin_grant(self.v.gid,uid,days,i.user.id)
  self.v.bot.db.execute('UPDATE licenses SET max_activations=? WHERE code=?',(acts,code))
  self.v.bot.db.execute('INSERT INTO license_orders(order_id,guild_id,user_id,license_code,status,note,created_by) VALUES(?,?,?,?,?,?,?)',(order,self.v.gid,uid,code,'issued',str(self.note.value)[:120],i.user.id))
  ok=await self.v.bot.deliver_license(self.v.gid,uid,code,None,exp)
  await i.followup.send(('✅' if ok else '⚠️')+f' **{order}** generated for <@{uid}>. '+('License + activation GUI were sent to THEIR DM.' if ok else 'License was created, but Discord blocked their DM.'),ephemeral=True)

class CustomerSelect(discord.ui.UserSelect):
 def __init__(self,v):super().__init__(placeholder='1. Select the customer…',min_values=1,max_values=1,row=0);self.v=v
 async def callback(self,i):self.v.user_id=self.values[0].id;await i.response.send_message(f'Customer selected: {self.values[0].mention}. Now click **Generate License**.',ephemeral=True)

class LicenseGeneratorView(discord.ui.View):
 def __init__(self,bot,gid):super().__init__(timeout=None);self.bot=bot;self.gid=gid;self.user_id=None;self.add_item(CustomerSelect(self))
 async def interaction_check(self,i):
  s=self.bot.db.guild(self.gid)
  if not is_admin_member(i.user,s):await i.response.send_message('Administrator access is required.',ephemeral=True);return False
  return True
 @discord.ui.button(label='Generate License',emoji='🔑',style=discord.ButtonStyle.green,custom_id='420vault:licensegen:generate',row=1)
 async def generate(self,i,b):
  if not self.user_id:return await i.response.send_message('Select the customer first.',ephemeral=True)
  await i.response.send_modal(GrantModal(self))

async def ensure_license_generator_panel(bot,guild,channel):
 try:
  # Restrict the channel to administrators while preserving server owner access.
  await channel.set_permissions(guild.default_role,view_channel=False,reason='420Vault license generator privacy')
  if guild.me:await channel.set_permissions(guild.me,view_channel=True,send_messages=True,read_message_history=True,reason='420Vault license generator')
  st=bot.db.guild(guild.id);rid=st.get('overseer_role_id') or st.get('admin_role_id');role=guild.get_role(int(rid)) if rid else None
  if role:await channel.set_permissions(role,view_channel=True,send_messages=True,read_message_history=True,reason='420Vault license generator admin role')
  async for m in channel.history(limit=50):
   if m.author==bot.user and m.embeds and m.embeds[0].title=='🔑 420Vault License Generator':
    await m.edit(embed=panel_embed(),view=LicenseGeneratorView(bot,guild.id));return m
  m=await channel.send(embed=panel_embed(),view=LicenseGeneratorView(bot,guild.id))
  try:await m.pin(reason='420Vault license generator')
  except discord.HTTPException:pass
  return m
 except (discord.Forbidden,discord.HTTPException):return None

def panel_embed():
 e=discord.Embed(title='🔑 420Vault License Generator',description='**1. Select the customer.**\n**2. Click Generate License.**\n**3. Choose access length and activation limit.**\n\nThe license and activation GUI are delivered to the **selected customer’s DM**, never the administrator’s DM.',color=discord.Color.green())
 e.add_field(name='Order IDs',value='Every GUI-issued license receives an `ORD-...` reference linking the issuance to the customer and license.',inline=False);return e
