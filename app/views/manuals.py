from __future__ import annotations
from pathlib import Path
import discord
USER_SECTIONS={
'Getting Started':'Run `420_tos` to verify and `420_help` for commands. Use `420_subscribe` when paid access is required.\n\nSearch: `420_search` = managed links; `420_vault_search` = Physical Vault; `420_drive_search` = Google Drive; `420_server_search` = Remote File Servers.',
'Search & Downloads':'Each storage source is separate. Audio results can expose Preview Audio. Discord uploads obey the server upload limit; Drive/remote sources can provide direct links.',
'Licenses & Payments':'Activate licenses through the bot button/modal. `420_subscribe` opens plans. Cash App is manual approval; Stripe/PayPal use hosted checkout when enabled.',
'Tickets & Problems':'Use the Support Center for bugs/payment/resource help. If a GUI expires, run its command again. Offline Physical Vault metadata remains searchable but cannot be delivered until storage returns.'}
ADMIN_SECTIONS={
'First Setup':'Run `420_admin` → Diagnostics, then configure Channels, Access Roles, Terms, storage sources, search, subscriptions/payments, and licensing. Test with a non-admin account.',
'Physical Vault':'Admin → Vault Storage. Configure Path, Test, Scan Changes, Full Reindex, Stats. v5.5 preserves indexed metadata when storage goes offline; scans mark unseen records unavailable rather than deleting the index.',
'Web Scraper':'Admin → Link Library & Scraper → New Web Scrape. v5.5 shows a live dashboard with pages, links, errors, queue and recent discoveries. Finish by creating/merging a managed list or exporting TXT.',
'Remote Servers':'Admin → Remote File Servers. Configure an HTTPS JSON manifest server, test it, sync it, and let users search it with `420_server_search`.',
'TOS & Access':'Every verification session randomly samples questions and randomizes answer order. Map TOS Accepted, Verified, Unverified, Paid Member, Beta Tester, and optional custom-admin roles under Access Roles. Mappings are stored by Discord role ID.',
'Payments & Licensing':'Plans define price/duration/provider IDs. Cash App is manual; Stripe/PayPal require server-side credentials and webhooks. Never expose signing/API/payment secrets.'}
class ManualSelect(discord.ui.Select):
 def __init__(self,v):self.v=v;super().__init__(placeholder='Choose a manual section…',options=[discord.SelectOption(label=k,value=k) for k in v.sections])
 async def callback(self,i):self.v.section=self.values[0];await i.response.edit_message(embed=self.v.embed(),view=self.v)
class ManualView(discord.ui.View):
 def __init__(self,owner_id,admin=False):super().__init__(timeout=900);self.owner_id=owner_id;self.admin=admin;self.sections=ADMIN_SECTIONS if admin else USER_SECTIONS;self.section=next(iter(self.sections));self.add_item(ManualSelect(self))
 def embed(self):
  e=discord.Embed(title='🛠️ 420Vault Admin Manual' if self.admin else '📘 420Vault User Manual',description=self.sections[self.section],color=discord.Color.dark_green());e.add_field(name='Section',value=self.section,inline=False);e.set_footer(text='420VaultBot v5.5.6 • Built-in manual');return e
 @discord.ui.button(label='User Manual PDF',emoji='📄',style=discord.ButtonStyle.secondary,row=2)
 async def pdf(self,i,b):
  if self.admin:return await i.response.send_message('The PDF button is for the user manual.',ephemeral=True)
  p=Path(__file__).resolve().parents[2]/'docs'/'420VaultBot_User_Manual_v5.5.6.pdf'
  if not p.is_file():return await i.response.send_message('User Manual PDF is missing from this installation.',ephemeral=True)
  await i.response.send_message(file=discord.File(p,filename=p.name),ephemeral=True)
 async def interaction_check(self,i):
  if i.user.id!=self.owner_id:await i.response.send_message('Open your own manual with the manual command.',ephemeral=True);return False
  return True
