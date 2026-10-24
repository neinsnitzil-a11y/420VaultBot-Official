from __future__ import annotations
import asyncio
import discord

from app.services.server_bootstrap import ensure_server_bootstrap, create_recommended_roles

# Every routable utility in the guided setup. The DB already supports arbitrary
# guild_channels purposes, so this does not require destructive schema changes.
UTILITY_ROUTES = (
    ('search','General / fallback commands','🎛️'),
    ('help','Help & manuals','❓'),
    ('account','Account / login commands','🔐'),
    ('profile','Profiles & public profile search','👤'),
    ('links','Link search','🔗'),
    ('vault','Physical Vault','💾'),
    ('drive','Google Drive','☁️'),
    ('remote','Remote file servers','🖥️'),
    ('subscription','Subscriptions / checkout','💳'),
    ('admin','Administrator commands','🛠️'),
    ('tos','Terms onboarding','📜'),
    ('license','License activation','🔑'),
    ('tickets','Support / payment tickets','🎫'),
    ('logs','Audit / bot logs','📋'),
)
ROUTE_LABELS={k:(label,emoji) for k,label,emoji in UTILITY_ROUTES}

ROLE_FIELDS=(
    ('admin_role_id','Vault Administrator / Overseer'),
    ('verified_role_id','Terms Accepted'),
    ('member_role_id','Licensed / Verified Member'),
    ('unverified_role_id','Unverified'),
    ('subscribed_role_id','Subscribed / Paid Member'),
    ('beta_role_id','Beta Tester'),
    ('overseer_role_id','Vault Overseer'),
)


def admin_ok(i:discord.Interaction):
    if not isinstance(i.user,discord.Member):return False
    if i.user.guild_permissions.administrator or i.guild.owner_id==i.user.id:return True
    s=i.client.db.guild(i.guild_id)
    ids={s.get('admin_role_id'),s.get('overseer_role_id')}
    ids.discard(None)
    return any(r.id in ids for r in i.user.roles)


def _mention_channels(guild,ids):
    vals=[]
    for cid in ids:
        ch=guild.get_channel(int(cid)) if guild else None
        vals.append(ch.mention if ch else f'`missing:{cid}`')
    return ' '.join(vals) if vals else 'Not configured'


class SetupSectionSelect(discord.ui.Select):
    def __init__(self,view):
        opts=[discord.SelectOption(label='Setup Overview',value='overview',emoji='🏠'),
              discord.SelectOption(label='Automatic Server Build / Repair',value='autobuild',emoji='🏗️'),
              discord.SelectOption(label='Role Mapping',value='roles',emoji='👥'),
              discord.SelectOption(label='Advanced Utility Configuration',value='advanced',emoji='🧰')]
        opts += [discord.SelectOption(label=label,value=f'route:{key}',emoji=emoji) for key,label,emoji in UTILITY_ROUTES]
        opts += [discord.SelectOption(label='Configuration Checklist',value='checklist',emoji='✅')]
        super().__init__(placeholder='Choose a setup area…',options=opts[:25],min_values=1,max_values=1,row=0)
        self.setup_view=view
    async def callback(self,i):
        self.setup_view.section=self.values[0]
        self.setup_view.rebuild()
        await i.response.edit_message(embed=self.setup_view.embed(i.guild),view=self.setup_view)


class UtilityChannelSelect(discord.ui.ChannelSelect):
    def __init__(self,parent,purpose):
        label,emoji=ROUTE_LABELS[purpose]
        super().__init__(placeholder=f'{emoji} {label}: choose 1-25 channel(s)',channel_types=[discord.ChannelType.text],min_values=1,max_values=25,row=1)
        self.setup_view=parent;self.purpose=purpose
    async def callback(self,i):
        await i.response.defer(ephemeral=True,thinking=True)
        ids=[x.id for x in self.values]
        await asyncio.to_thread(self.setup_view.bot.db.set_channels,self.setup_view.gid,self.purpose,ids)
        # Mirror canonical single-channel settings used by persistent panels.
        first=ids[0]
        mirror={'tos':'tos_channel_id','license':'license_channel_id','tickets':'ticket_channel_id','logs':'log_channel_id'}
        if self.purpose in mirror:
            await asyncio.to_thread(self.setup_view.bot.db.set_guild,self.setup_view.gid,**{mirror[self.purpose]:first})
        if self.purpose=='search':
            await asyncio.to_thread(self.setup_view.bot.db.set_channels,self.setup_view.gid,'search',ids)
            await self.setup_view.bot.ensure_command_panels(self.setup_view.gid,force=True)
        elif self.purpose=='license':await self.setup_view.bot.ensure_license_panel(self.setup_view.gid,force=True)
        elif self.purpose=='tickets':await self.setup_view.bot.ensure_ticket_panel(self.setup_view.gid,force=True)
        await asyncio.to_thread(self.setup_view.bot.db.audit,self.setup_view.gid,i.user.id,'setup_route',f'{self.purpose}={ids}')
        await i.followup.send(f'✅ **{ROUTE_LABELS[self.purpose][0]}** is now restricted to: '+', '.join(x.mention for x in self.values),ephemeral=True)


class RoleMappingSelect(discord.ui.RoleSelect):
    def __init__(self,parent,key,label):
        super().__init__(placeholder=f'Map role: {label}',min_values=1,max_values=1,row=2)
        self.setup_view=parent;self.key=key;self.label_text=label
    async def callback(self,i):
        await i.response.defer(ephemeral=True,thinking=True)
        role=self.values[0]
        await asyncio.to_thread(self.setup_view.bot.db.set_guild,self.setup_view.gid,**{self.key:role.id})
        await asyncio.to_thread(self.setup_view.bot.db.audit,self.setup_view.gid,i.user.id,'setup_role',f'{self.key}={role.id}')
        await i.followup.send(f'✅ **{self.label_text}** mapped to {role.mention}.',ephemeral=True)


class SetupRoleFieldSelect(discord.ui.Select):
    def __init__(self,parent):
        super().__init__(placeholder='Choose which access role to map…',options=[discord.SelectOption(label=label,value=key) for key,label in ROLE_FIELDS],row=1)
        self.setup_view=parent
    async def callback(self,i):
        self.setup_view.role_key=self.values[0]
        self.setup_view.rebuild()
        await i.response.edit_message(embed=self.setup_view.embed(i.guild),view=self.setup_view)


class SetupActionButton(discord.ui.Button):
    def __init__(self,parent,label,emoji,action,style=discord.ButtonStyle.secondary,row=2):
        super().__init__(label=label,emoji=emoji,style=style,row=row);self.setup_view=parent;self.action=action
    async def callback(self,i):
        if self.action=='autobuild':
            await i.response.defer(ephemeral=True,thinking=True)
            try:
                roles=await create_recommended_roles(self.setup_view.bot,i.guild)
                found=await ensure_server_bootstrap(self.setup_view.bot,i.guild)
                # Auto-map sensible defaults, without removing custom mappings.
                audio_names={'420vaultbot-cheetheet-and-commands','beats','zenology-bank','serum-1-and-2-banks','portal-banks','gross-beat-presets','midi','omnisphere-bank','fx-sounds','presets-banks','loops','one-shots','🥁-drumkits-sounds','🔓-cracked-plugins','🔓keygens'}
                audio=[c.id for c in i.guild.text_channels if c.name.casefold() in {x.casefold() for x in audio_names}]
                if audio:
                    for p in ('search','links','vault','drive','remote'):await asyncio.to_thread(self.setup_view.bot.db.set_channels,self.setup_view.gid,p,audio)
                name_map={'login':'account','terms':'tos','license':'license','tickets':'tickets','logs':'logs','license-generator':'admin'}
                for name,purpose in name_map.items():
                    ch=found.get(name)
                    if ch:await asyncio.to_thread(self.setup_view.bot.db.set_channels,self.setup_view.gid,purpose,[ch.id])
                test=discord.utils.get(i.guild.text_channels,name='🧪-bot-testing') or discord.utils.get(i.guild.text_channels,name='bot-testing')
                if test:await asyncio.to_thread(self.setup_view.bot.db.set_channels,self.setup_view.gid,'admin',[test.id])
                await asyncio.to_thread(self.setup_view.bot.db.audit,self.setup_view.gid,i.user.id,'setup_autobuild','created/reused recommended roles/channels and seeded utility routing')
                await i.followup.send(f'✅ **Recommended server structure synchronized.**\nChannels ready: **{len(found)}**\nRoles checked/created: **{len(roles)}**\n\nReview each utility route in `420_setup` before finishing.',ephemeral=True)
            except Exception as e:await i.followup.send(f'❌ Automatic setup failed: `{type(e).__name__}: {str(e)[:900]}`',ephemeral=True)
            return
        if self.action=='create_roles':
            await i.response.defer(ephemeral=True,thinking=True)
            try:
                roles=await create_recommended_roles(self.setup_view.bot,i.guild)
                created=[r.mention for r,new in roles.values() if new]
                await i.followup.send('✅ Recommended roles synchronized.'+('\nCreated: '+', '.join(created) if created else '\nNo missing roles needed creation.'),ephemeral=True)
            except Exception as e:await i.followup.send(f'❌ Could not create roles: `{e}`',ephemeral=True)
            return
        if self.action=='ensure_panels':
            await i.response.defer(ephemeral=True,thinking=True)
            try:
                await self.setup_view.bot.ensure_command_panels(self.setup_view.gid,force=True)
                await self.setup_view.bot.ensure_license_panel(self.setup_view.gid,force=True)
                await self.setup_view.bot.ensure_ticket_panel(self.setup_view.gid,force=True)
                await i.followup.send('✅ Persistent Command Center, License and Ticket panels were refreshed where configured.',ephemeral=True)
            except Exception as e:await i.followup.send(f'❌ Panel refresh failed: `{e}`',ephemeral=True)
            return
        if self.action.startswith('admin_section:'):
            from app.views.admin import AdminView
            section=self.action.split(':',1)[1]
            v=AdminView(self.setup_view.bot,self.setup_view.gid,section)
            return await i.response.send_message(embed=v.embed(),view=v,ephemeral=True)
        if self.action=='finish':
            missing=await asyncio.to_thread(self.setup_view.missing,i.guild)
            if missing:return await i.response.send_message('⚠️ Setup is not complete yet:\n'+'\n'.join(f'• {x}' for x in missing),ephemeral=True)
            await i.response.defer(ephemeral=True,thinking=True)
            await asyncio.to_thread(self.setup_view.bot.db.set_guild,self.setup_view.gid,setup_completed=1)
            await asyncio.to_thread(self.setup_view.bot.db.audit,self.setup_view.gid,i.user.id,'setup_complete','guided setup checklist passed')
            return await i.followup.send('✅ **420VaultBot setup marked complete.** Run `420_admin` for advanced provider, Vault, Drive, payment, security and maintenance configuration.',ephemeral=True)


class SetupView(discord.ui.View):
    """v6.5 guided setup: role creation, channel creation/mapping and utility routing."""
    def __init__(self,bot,gid,section='overview'):
        super().__init__(timeout=1800);self.bot=bot;self.gid=gid;self.section=section;self.role_key=ROLE_FIELDS[0][0];self.rebuild()
    async def interaction_check(self,i):
        if admin_ok(i):return True
        await i.response.send_message('Administrator/owner/Vault Overseer access is required.',ephemeral=True);return False
    def rebuild(self):
        self.clear_items();self.add_item(SetupSectionSelect(self))
        if self.section.startswith('route:'):
            self.add_item(UtilityChannelSelect(self,self.section.split(':',1)[1]))
        elif self.section=='roles':
            self.add_item(SetupRoleFieldSelect(self));label=dict(ROLE_FIELDS)[self.role_key];self.add_item(RoleMappingSelect(self,self.role_key,label))
            self.add_item(SetupActionButton(self,'Create Missing Recommended Roles','➕','create_roles',discord.ButtonStyle.success,row=3))
        elif self.section=='autobuild':
            self.add_item(SetupActionButton(self,'Create / Repair Recommended Structure','🏗️','autobuild',discord.ButtonStyle.success,row=1))
            self.add_item(SetupActionButton(self,'Refresh Persistent Panels','📌','ensure_panels',discord.ButtonStyle.primary,row=1))
        elif self.section=='advanced':
            advanced=[('Vault','💾','vault'),('Drive','☁️','drive'),('Search','🔎','search'),('Links','🔗','links'),('Remote','🖥️','remote'),('Terms','📜','tos'),('Licensing','🔑','licensing'),('Subscriptions','📅','subscriptions'),('Payments','💳','payments'),('Security','🛡️','security'),('Audio','🔊','audio'),('Updates','⬆️','updates'),('Diagnostics','🩺','diagnostics')]
            for idx,(label,emoji,section) in enumerate(advanced):
                self.add_item(SetupActionButton(self,label,emoji,'admin_section:'+section,discord.ButtonStyle.secondary,row=1+(idx//5)))
        elif self.section=='checklist':
            self.add_item(SetupActionButton(self,'Mark Setup Complete','✅','finish',discord.ButtonStyle.success,row=1))
    def missing(self,guild):
        s=self.bot.db.guild(self.gid);missing=[]
        required_routes=('search','account','profile','links','vault','drive','subscription','admin','tos','license','tickets','logs')
        for purpose in required_routes:
            if not self.bot.db.channels(self.gid,purpose):missing.append(f'No channel route configured for **{ROUTE_LABELS[purpose][0]}**')
        for key,label in ROLE_FIELDS[:6]:
            if not s.get(key):missing.append(f'Role not mapped: **{label}**')
        return missing
    def embed(self,guild):
        s=self.bot.db.guild(self.gid)
        e=discord.Embed(title='⚙️ 420VaultBot Guided Setup',color=discord.Color.dark_green())
        if self.section=='overview':
            e.description='Configure the bot from the ground up. Every utility can be linked to its own allowed Discord channel(s). Users cannot launch that utility outside its configured route. Use **Automatic Server Build / Repair** for a starting structure, then review every route.'
            configured=sum(bool(self.bot.db.channels(self.gid,p)) for p,_,_ in UTILITY_ROUTES)
            e.add_field(name='Channel routing',value=f'**{configured}/{len(UTILITY_ROUTES)}** utility routes configured',inline=False)
            e.add_field(name='Roles',value='Admin/Overseer • Terms Accepted • Licensed Member • Unverified • Paid Member • Beta Tester',inline=False)
            e.add_field(name='Advanced configuration',value='After this guided setup, use `420_admin` for Vault paths, Google OAuth, remote servers, scraper/link AV, audio previews, subscription plans, Stripe/PayPal/Cash App, SMTP, backups, updates and diagnostics.',inline=False)
        elif self.section=='autobuild':
            e.description='Create/reuse the recommended 420Vault channels and roles, initialize Terms/Login/License/Ticket panels, and seed sensible routing. **Existing channels are reused by name; existing custom mappings are not intentionally deleted.**'
            e.add_field(name='Recommended channels',value='Audio Vault content channels • `terms` • `login` • `license` • `license-generator` • `logs` • `tickets`',inline=False)
            e.add_field(name='Recommended roles',value='TOS Accepted • Verified • Unverified • Paid Member • Beta Tester',inline=False)
        elif self.section=='roles':
            label=dict(ROLE_FIELDS)[self.role_key];rid=s.get(self.role_key);role=guild.get_role(rid) if guild and rid else None
            e.description='Map the actual Discord roles used by access control. The setup stores IDs; it does not depend on role names.'
            e.add_field(name='Currently editing',value=f'**{label}** → {role.mention if role else "Not mapped"}',inline=False)
        elif self.section.startswith('route:'):
            purpose=self.section.split(':',1)[1];label,emoji=ROUTE_LABELS[purpose];ids=self.bot.db.channels(self.gid,purpose)
            e.title=f'{emoji} Setup • {label}'
            e.description='Choose every text channel where this utility may be launched. This route is enforced for prefix commands and help/command buttons.'
            e.add_field(name='Current allowed channel(s)',value=_mention_channels(guild,ids),inline=False)
            if purpose=='admin':e.add_field(name='Admin note',value='Administrators/owners/overseers still need admin permission **and** an active 420Vault admin session. Bot-testing is also supported as a portable fallback.',inline=False)
        elif self.section=='advanced':
            e.description='Finish the detailed configuration for every utility without leaving the setup workflow. Each button opens the corresponding `420_admin` control panel privately.'
            e.add_field(name='Storage & search',value='Physical Vault • Google Drive • search/delivery • link library/scraper • remote servers',inline=False)
            e.add_field(name='Access & commerce',value='Terms • licensing • subscription plans • Stripe / PayPal / Cash App • transactions',inline=False)
            e.add_field(name='Security & operations',value='SMTP • Link/Upload AV • audio previews • backups/updates • diagnostics',inline=False)
        elif self.section=='checklist':
            missing=self.missing(guild);e.description='Final setup validation. Advanced integrations may still require configuration in `420_admin`.'
            e.add_field(name='Result',value=('✅ Core setup checklist passed.' if not missing else '⚠️ '+str(len(missing))+' item(s) still need attention.'),inline=False)
            if missing:e.add_field(name='Missing / incomplete',value='\n'.join('• '+x for x in missing[:15]),inline=False)
        e.set_footer(text='420VaultBot v6.5.3 • Guided Setup • all mappings are per-server')
        return e
