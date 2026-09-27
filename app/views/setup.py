from __future__ import annotations
import discord

def admin_ok(i:discord.Interaction):
 if not isinstance(i.user,discord.Member):return False
 if i.user.guild_permissions.administrator:return True
 s=i.client.db.guild(i.guild_id);rid=s.get('admin_role_id')
 return bool(rid and any(r.id==rid for r in i.user.roles))

class MultiSearchChannels(discord.ui.ChannelSelect):
 def __init__(self,bot,gid):
  super().__init__(placeholder='Allowed search/delivery channels (choose 1-25)',channel_types=[discord.ChannelType.text],min_values=1,max_values=25,row=0);self.bot=bot;self.gid=gid
 async def callback(self,i):
  if not admin_ok(i):return await i.response.send_message('Administrator access is required.',ephemeral=True)
  ids=[x.id for x in self.values];self.bot.db.set_channels(self.gid,'search',ids)
  await i.response.send_message('✅ Allowed search channels: '+', '.join(x.mention for x in self.values),ephemeral=True)
class SingleChannel(discord.ui.ChannelSelect):
 def __init__(self,bot,gid,key,label,row):super().__init__(placeholder=label,channel_types=[discord.ChannelType.text],min_values=1,max_values=1,row=row);self.bot=bot;self.gid=gid;self.key=key
 async def callback(self,i):
  if not admin_ok(i):return await i.response.send_message('Administrator access is required.',ephemeral=True)
  ch=self.values[0];self.bot.db.set_guild(self.gid,**{self.key:ch.id})
  if self.key=='license_channel_id':await self.bot.ensure_license_panel(self.gid,force=True)
  await i.response.send_message(f'✅ {self.placeholder} set to {ch.mention}.',ephemeral=True)
class RoleSelect(discord.ui.RoleSelect):
 def __init__(self,bot,gid,key,label,row):super().__init__(placeholder=label,min_values=1,max_values=1,row=row);self.bot=bot;self.gid=gid;self.key=key
 async def callback(self,i):
  if not admin_ok(i):return await i.response.send_message('Administrator access is required.',ephemeral=True)
  self.bot.db.set_guild(self.gid,**{self.key:self.values[0].id});await i.response.send_message(f'✅ {self.placeholder}: {self.values[0].mention}',ephemeral=True)
class SetupView(discord.ui.View):
 def __init__(self,bot,gid):
  super().__init__(timeout=900);self.bot=bot;self.gid=gid
  self.add_item(MultiSearchChannels(bot,gid));self.add_item(SingleChannel(bot,gid,'license_channel_id','License activation channel',1));self.add_item(SingleChannel(bot,gid,'log_channel_id','Audit/log channel',2));self.add_item(RoleSelect(bot,gid,'admin_role_id','Vault administrator role',3));self.add_item(RoleSelect(bot,gid,'member_role_id','Licensed member role',4))
 async def interaction_check(self,i):
  if admin_ok(i):return True
  await i.response.send_message('Administrator access is required.',ephemeral=True);return False
