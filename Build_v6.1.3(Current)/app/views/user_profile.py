from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import discord


def _fmt_ts(value):
    try:
        return f'<t:{int(value)}:D>'
    except Exception:
        return 'Unknown'


def _safe(v, fallback='Not set'):
    v = str(v or '').strip()
    return v if v else fallback


def profile_embed(bot, guild: discord.Guild, member: discord.Member, viewer_id: int):
    data = bot.profiles.summary(guild.id, member.id)
    if not data:
        return discord.Embed(title='👤 420Vault Profile', description='This member has not created a 420Vault account.', color=discord.Color.dark_grey()), False
    p, a = data['profile'], data['account']
    owner = viewer_id == member.id
    public = bool(p.get('public_profile'))
    if not owner and not public:
        return discord.Embed(title='🔒 Private 420Vault Profile', description=f'{member.mention} has chosen to keep their profile private.', color=discord.Color.dark_grey()), False

    title = _safe(p.get('display_name'), member.display_name)
    e = discord.Embed(title=f'👤 {title}', description=_safe(p.get('bio'), 'No bio added yet.'), color=discord.Color.dark_green())
    e.set_author(name=f'420Vault Profile • @{a["username"]}')
    if member.display_avatar:
        e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name='🎵 Creator / Artist', value=_safe(p.get('creator_name')), inline=True)
    e.add_field(name='🎚️ DAW', value=_safe(p.get('daw')), inline=True)
    e.add_field(name='🎼 Genres', value=_safe(p.get('genres')), inline=True)
    e.add_field(name='🌐 Website', value=_safe(p.get('website')), inline=False)
    e.add_field(name='🔗 Socials', value=_safe(p.get('socials')), inline=False)
    e.add_field(name='🎯 Interests', value=_safe(p.get('interests')), inline=False)
    e.add_field(name='🕒 Timezone', value=_safe(p.get('timezone')), inline=True)
    e.add_field(name='📅 Member Since', value=_fmt_ts(a.get('created_at')), inline=True)
    e.add_field(name='👁️ Visibility', value='Public' if public else 'Private', inline=True)

    if owner:
        sub = data['subscription']
        ent = data['entitlement']
        lic = data['license']
        if sub:
            access = f'Plan: **{sub.get("plan_name","Subscription")}**\nStatus: **{sub.get("status","active")}**\nExpires: **{sub.get("expires_at") or "Never"}**'
        elif ent:
            access = f'Access grant: **{ent.get("status","active")}**\nExpires: **{ent.get("expires_at") or "Never"}**'
        else:
            access = 'No active subscription or admin grant.'
        e.add_field(name='🎟️ My Access', value=access, inline=False)
        e.add_field(name='🔐 Account Security', value=f'Email verified: **{"Yes" if a.get("email_verified") else "No"}**\nAuthenticator 2FA: **{"Enabled" if a.get("totp_enabled") else "Disabled"}**', inline=True)
        e.add_field(name='🔑 License', value=(f'`{lic["code"]}` • **{lic["status"]}**' if lic else 'No license issued'), inline=True)
        e.set_footer(text='Only you can see the security, license, and subscription details on your profile.')
    else:
        e.set_footer(text='Public 420Vault profile • Security/email/license details are never shown to other members.')
    return e, owner


class EditProfileModal(discord.ui.Modal, title='Edit 420Vault Profile'):
    display_name = discord.ui.TextInput(label='Display name', required=False, max_length=80)
    creator_name = discord.ui.TextInput(label='Producer / Artist name', required=False, max_length=80)
    bio = discord.ui.TextInput(label='Bio / About me', required=False, max_length=1000, style=discord.TextStyle.paragraph)
    website = discord.ui.TextInput(label='Website', required=False, max_length=300, placeholder='https://your-site.com')
    genres = discord.ui.TextInput(label='Genres', required=False, max_length=250, placeholder='Trap, R&B, Hip-Hop...')
    def __init__(self, bot, gid, uid):
        super().__init__(timeout=300); self.bot=bot; self.gid=gid; self.uid=uid
        p=bot.profiles.ensure(gid,uid) or {}
        self.display_name.default=p.get('display_name') or None; self.creator_name.default=p.get('creator_name') or None
        self.bio.default=p.get('bio') or None; self.website.default=p.get('website') or None; self.genres.default=p.get('genres') or None
    async def on_submit(self, i):
        try:
            await asyncio.to_thread(self.bot.profiles.update_main,self.gid,self.uid,display_name=str(self.display_name),creator_name=str(self.creator_name),bio=str(self.bio),website=str(self.website),genres=str(self.genres))
            e,_=profile_embed(self.bot,i.guild,i.user,i.user.id)
            await i.response.send_message('✅ Profile updated.',embed=e,view=UserProfileView(self.bot,self.gid,self.uid),ephemeral=True)
        except Exception as exc: await i.response.send_message(f'❌ {exc}',ephemeral=True)


class EditProfileDetailsModal(discord.ui.Modal, title='Edit Profile Details'):
    daw = discord.ui.TextInput(label='DAW / production setup', required=False, max_length=150, placeholder='FL Studio, Ableton, Logic...')
    socials = discord.ui.TextInput(label='Social links / handles', required=False, max_length=500, style=discord.TextStyle.paragraph)
    timezone = discord.ui.TextInput(label='Timezone', required=False, max_length=80, placeholder='EST / America-New_York')
    interests = discord.ui.TextInput(label='Production interests', required=False, max_length=300, placeholder='Sound design, mixing, drum kits...')
    def __init__(self,bot,gid,uid):
        super().__init__(timeout=300); self.bot=bot; self.gid=gid; self.uid=uid
        p=bot.profiles.ensure(gid,uid) or {}
        self.daw.default=p.get('daw') or None; self.socials.default=p.get('socials') or None
        self.timezone.default=p.get('timezone') or None; self.interests.default=p.get('interests') or None
    async def on_submit(self,i):
        await asyncio.to_thread(self.bot.profiles.update_details,self.gid,self.uid,daw=str(self.daw),socials=str(self.socials),timezone=str(self.timezone),interests=str(self.interests))
        e,_=profile_embed(self.bot,i.guild,i.user,i.user.id)
        await i.response.send_message('✅ Profile details updated.',embed=e,view=UserProfileView(self.bot,self.gid,self.uid),ephemeral=True)


class UserProfileView(discord.ui.View):
    def __init__(self, bot, gid:int, uid:int):
        super().__init__(timeout=900); self.bot=bot; self.gid=gid; self.uid=uid
    async def interaction_check(self,i):
        if i.user.id==self.uid:return True
        await i.response.send_message('Open your own profile page to edit it.',ephemeral=True);return False
    @discord.ui.button(label='Edit Profile',emoji='✏️',style=discord.ButtonStyle.primary)
    async def edit(self,i,b): await i.response.send_modal(EditProfileModal(self.bot,self.gid,self.uid))
    @discord.ui.button(label='Edit Details',emoji='🎚️',style=discord.ButtonStyle.secondary)
    async def details(self,i,b): await i.response.send_modal(EditProfileDetailsModal(self.bot,self.gid,self.uid))
    @discord.ui.button(label='Toggle Public / Private',emoji='👁️',style=discord.ButtonStyle.secondary)
    async def visibility(self,i,b):
        p=await asyncio.to_thread(self.bot.profiles.ensure,self.gid,self.uid);new=not bool(p.get('public_profile'))
        await asyncio.to_thread(self.bot.profiles.set_public,self.gid,self.uid,new)
        e,_=profile_embed(self.bot,i.guild,i.user,i.user.id)
        await i.response.edit_message(content=f'Profile is now **{"Public" if new else "Private"}**.',embed=e,view=UserProfileView(self.bot,self.gid,self.uid))
    @discord.ui.button(label='Refresh',emoji='🔄',style=discord.ButtonStyle.secondary)
    async def refresh(self,i,b):
        e,_=profile_embed(self.bot,i.guild,i.user,i.user.id);await i.response.edit_message(embed=e,view=UserProfileView(self.bot,self.gid,self.uid))


async def send_profile(ctx, member=None):
    member = member or ctx.author
    e, owner = profile_embed(ctx.bot, ctx.guild, member, ctx.author.id)
    await ctx.send(embed=e, view=UserProfileView(ctx.bot, ctx.guild.id, member.id) if owner else None)
