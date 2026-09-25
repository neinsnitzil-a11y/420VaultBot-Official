from __future__ import annotations
import discord

DEFAULT_CHANNELS=['zenology-bank','serum-1-and-2-banks','portal-banks','midi','gross-beat-presets','omnisphere-bank','loops','fx-sounds','presets-banks','🥁-drumkits-sounds','one-shots','🔓-cracked-plugins','🔓keygens','terms','license','license-generator','logs','tickets']
ROLE_KEYS=(
    'verified_role_id','member_role_id','unverified_role_id','subscribed_role_id','beta_role_id','overseer_role_id'
)

async def _ensure_roles(bot,guild:discord.Guild):
    """Validate configured role IDs only. Never guess roles by name or auto-create them.

    v5.5.6 is portable: each guild maps its own existing roles in Setup/Admin.
    Recommended roles are created only after an administrator explicitly requests it.
    """
    settings=bot.db.guild(guild.id); found={}; stale=[]
    for key in ROLE_KEYS:
        rid=settings.get(key)
        if not rid: continue
        role=guild.get_role(int(rid))
        if role: found[key]=role
        else: stale.append(key)
    if stale:
        await bot.log_event(guild.id,'BOOTSTRAP','Configured role IDs no longer exist: '+', '.join(stale),level='ERROR')
    if not settings.get('verified_role_id') or not settings.get('unverified_role_id'):
        await bot.log_event(guild.id,'BOOTSTRAP','Access roles require configuration. Open 420_admin → Access Roles or 420_setup.',level='WARNING')
    return found

async def create_recommended_roles(bot,guild:discord.Guild):
    """Explicit admin action: create only missing roles required by core access flow."""
    if not guild.me or not guild.me.guild_permissions.manage_roles:
        raise discord.Forbidden(None,'Manage Roles permission is required')
    settings=bot.db.guild(guild.id); created={}; changes={}
    specs=(
        ('verified_role_id','TOS Accepted'),
        ('member_role_id','Verified'),
        ('unverified_role_id','Unverified'),
        ('subscribed_role_id','Paid Member'),
        ('beta_role_id','Beta Tester'),
    )
    for key,name in specs:
        current=guild.get_role(settings.get(key)) if settings.get(key) else None
        if current:
            created[key]=(current,False);continue
        role=await guild.create_role(name=name,reason='420Vault administrator requested recommended access roles')
        changes[key]=role.id;created[key]=(role,True)
    if changes: bot.db.set_guild(guild.id,**changes)
    return created

async def apply_onboarding_gate(bot,guild:discord.Guild,terms:discord.TextChannel|None=None):
    """Make #terms the onboarding destination for Unverified members.

    Discord cannot force-open a channel in a member's client, so v4 combines
    channel permissions with a direct channel link sent on join.
    """
    s=bot.db.guild(guild.id)
    unverified=guild.get_role(s.get('unverified_role_id')) if s.get('unverified_role_id') else None
    terms=terms or (guild.get_channel(s.get('tos_channel_id')) if s.get('tos_channel_id') else None)
    if not unverified or not isinstance(terms,discord.TextChannel): return (0,0)
    changed=failed=0
    for ch in guild.channels:
        if not isinstance(ch,(discord.TextChannel,discord.ForumChannel,discord.VoiceChannel,discord.StageChannel)): continue
        try:
            if ch.id==terms.id:
                await ch.set_permissions(unverified,view_channel=True,read_message_history=True,send_messages=True,reason='420Vault v4 onboarding destination')
            else:
                await ch.set_permissions(unverified,view_channel=False,reason='420Vault v4 onboarding gate')
            changed+=1
        except (discord.Forbidden,discord.HTTPException): failed+=1
    await bot.log_event(guild.id,'ONBOARDING',f'Onboarding gate synchronized: {changed} channels; {failed} failed.')
    return changed,failed

async def ensure_server_bootstrap(bot,guild:discord.Guild):
    await _ensure_roles(bot,guild)
    if not guild.me or not guild.me.guild_permissions.manage_channels:
        await bot.log_event(guild.id,'BOOTSTRAP','Missing Manage Channels permission; automatic channel setup skipped.',level='ERROR');return {}
    found={};existing={c.name.casefold():c for c in guild.text_channels}
    ticket_cat=discord.utils.get(guild.categories,name='420 BOT TICKETS')
    if not ticket_cat:
        try:ticket_cat=await guild.create_category('420 BOT TICKETS',reason='420Vault support tickets')
        except (discord.Forbidden,discord.HTTPException):ticket_cat=None
    for name in DEFAULT_CHANNELS:
        ch=existing.get(name.casefold())
        if ch is None:
            try:ch=await guild.create_text_channel(name,category=ticket_cat if name=='tickets' else None,reason='420Vault automatic server bootstrap')
            except (discord.Forbidden,discord.HTTPException) as exc:
                await bot.log_event(guild.id,'BOOTSTRAP',f'Could not create #{name}: {type(exc).__name__}',level='ERROR');continue
        if name=='tickets' and ticket_cat and ch.category_id!=ticket_cat.id:
            try:await ch.edit(category=ticket_cat,reason='420Vault ticket hub organization')
            except (discord.Forbidden,discord.HTTPException):pass
        found[name]=ch
    changes={}
    if found.get('terms'):changes['tos_channel_id']=found['terms'].id
    if found.get('license'):changes['license_channel_id']=found['license'].id
    if found.get('logs'):changes['log_channel_id']=found['logs'].id
    if found.get('tickets'):changes['ticket_channel_id']=found['tickets'].id
    if changes:bot.db.set_guild(guild.id,**changes)
    if found.get('terms') and bot.db.guild(guild.id).get('tos_enabled',1):
        from app.views.tos import publish_tos
        try:
            await publish_tos(bot,guild,found['terms'])
            await apply_onboarding_gate(bot,guild,found['terms'])
        except (discord.Forbidden,discord.HTTPException) as exc: await bot.log_event(guild.id,'BOOTSTRAP',f'Could not initialize Terms onboarding: {type(exc).__name__}',level='ERROR')
    if found.get('license'):await bot.ensure_license_panel(guild.id)
    if found.get('license-generator'):
        from app.views.license_generator import ensure_license_generator_panel
        await ensure_license_generator_panel(bot,guild,found['license-generator'])
    if found.get('tickets'):await bot.ensure_ticket_panel(guild.id)
    await bot.log_event(guild.id,'BOOTSTRAP',f'v4 server bootstrap synchronized; {len(found)}/{len(DEFAULT_CHANNELS)} channels ready.')
    return found
