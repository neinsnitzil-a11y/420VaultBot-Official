from __future__ import annotations
import re,discord
from app.core.security import is_admin
TYPES={'crash':('💥 Crash / Startup Problem','Bot crashes, startup failures, tracebacks, or unexpected shutdowns.'),'bug':('🐛 Bug Report','Something in 420Vault is not working as expected.'),'vault':('📦 Vault Request','Request a plugin, drumkit, one-shot, MIDI, preset/bank, expansion, loop, or other Vault resource.'),'feature':('✨ Feature Request','Suggest an improvement or new 420Vault capability.'),'request':('📝 General Request','Request help or another action from the 420Vault team.'),'payment':('💳 Payment Issue','Get help with a payment, renewal, subscription, or transaction.'),'other':('❓ Other','Anything that does not fit the other ticket types.')}
class TicketDetailsModal(discord.ui.Modal):
    subject=discord.ui.TextInput(label='Subject',max_length=100,placeholder='Short summary');details=discord.ui.TextInput(label='Details',style=discord.TextStyle.paragraph,max_length=1800,placeholder='Explain what happened or what you need. Include errors/steps when relevant.')
    def __init__(self,bot,kind):super().__init__(title=TYPES[kind][0]);self.bot=bot;self.kind=kind
    async def on_submit(self,i):
        await i.response.defer(ephemeral=True);ch=await create_support_ticket(self.bot,i.guild,i.user,self.kind,str(self.subject),str(self.details));await i.followup.send(f'✅ Ticket created: {ch.mention}',ephemeral=True)
class TicketTypeSelect(discord.ui.Select):
    def __init__(self,bot):self.bot=bot;super().__init__(placeholder='What do you need help with?',min_values=1,max_values=1,custom_id='420vault:support:type',options=[discord.SelectOption(label=v[0],description=v[1][:100],value=k) for k,v in TYPES.items()])
    async def callback(self,i):await i.response.send_modal(TicketDetailsModal(self.bot,self.values[0]))
class SupportTicketPanel(discord.ui.View):
    def __init__(self,bot):super().__init__(timeout=None);self.add_item(TicketTypeSelect(bot))
class SupportTicketActions(discord.ui.View):
    def __init__(self,bot):super().__init__(timeout=None);self.bot=bot
    @discord.ui.button(label='Close Ticket',emoji='🔒',style=discord.ButtonStyle.danger,custom_id='420vault:support:close')
    async def close_ticket(self,i,b):
        row=self.bot.db.one('SELECT * FROM support_tickets WHERE channel_id=? AND status="open"',(i.channel_id,))
        if not row:return await i.response.send_message('This is not an open 420Bot support ticket.',ephemeral=True)
        if i.user.id!=row['user_id'] and not is_admin(i,self.bot.db.guild(i.guild_id)):return await i.response.send_message('Only the ticket owner or a bot admin can close this ticket.',ephemeral=True)
        self.bot.db.execute("UPDATE support_tickets SET status='closed',closed_at=CURRENT_TIMESTAMP WHERE id=?",(row['id'],));await self.bot.log_event(i.guild_id,'TICKET',f'Support ticket #{row["id"]} closed by {i.user} ({i.user.id}).');await i.response.send_message('🔒 Ticket closed. This channel will be deleted.')
        try:await i.channel.delete(reason='420Vault support ticket closed')
        except (discord.Forbidden,discord.HTTPException):pass
async def create_support_ticket(bot,guild,user,kind,subject,details):
    existing=bot.db.one('SELECT channel_id FROM support_tickets WHERE guild_id=? AND user_id=? AND ticket_type=? AND status="open"',(guild.id,user.id,kind))
    if existing:
        ch=guild.get_channel(existing['channel_id'])
        if ch:return ch
    s=bot.db.guild(guild.id);hub=guild.get_channel(s.get('ticket_channel_id')) if s.get('ticket_channel_id') else None;cat=hub.category if isinstance(hub,discord.TextChannel) and hub.category else discord.utils.get(guild.categories,name='420 BOT TICKETS')
    if not cat:cat=await guild.create_category('420 BOT TICKETS',reason='420Vault support tickets')
    ow={guild.default_role:discord.PermissionOverwrite(view_channel=False),guild.me:discord.PermissionOverwrite(view_channel=True,send_messages=True,manage_channels=True,read_message_history=True)};member=guild.get_member(user.id) or user;ow[member]=discord.PermissionOverwrite(view_channel=True,send_messages=True,attach_files=True,read_message_history=True)
    for rid in (s.get('admin_role_id'),s.get('overseer_role_id')):
        role=guild.get_role(rid) if rid else None
        if role:ow[role]=discord.PermissionOverwrite(view_channel=True,send_messages=True,read_message_history=True,manage_messages=True)
    safe=re.sub(r'[^a-z0-9-]','-',getattr(user,'name','user').lower())[:20].strip('-') or 'user';ch=await guild.create_text_channel(f'{kind}-{safe}',category=cat,overwrites=ow,reason='420Vault support ticket');tid=bot.db.execute('INSERT INTO support_tickets(guild_id,user_id,channel_id,ticket_type,subject,status) VALUES(?,?,?,?,?,"open")',(guild.id,user.id,ch.id,kind,subject[:100]));title,_=TYPES[kind];e=discord.Embed(title=f'{title} • Ticket #{tid}',description=details,color=discord.Color.blurple());e.add_field(name='Opened by',value=f'{user.mention} (`{user.id}`)',inline=False);e.add_field(name='Subject',value=subject[:100],inline=False);e.set_footer(text='420Vault Support • Use Close Ticket when resolved');await ch.send(content=user.mention,embed=e,view=SupportTicketActions(bot));await bot.log_event(guild.id,'TICKET',f'Opened {kind} ticket #{tid} by {user} ({user.id}) in #{ch.name}.');return ch
def ticket_panel_embed():return discord.Embed(title='🎫 420Bot Support Center',description='Open one private ticket for the issue you need help with.\n\n**Available:** crashes/startup problems, bug reports, Vault resource requests, feature requests, general requests, payment/support issues, and Other.\n\nFor Vault requests, describe the plugin, drumkit, one-shot, MIDI, preset/bank, expansion, loop, or other resource as precisely as possible.',color=discord.Color.blurple())
