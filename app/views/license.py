from __future__ import annotations
from datetime import datetime, timezone
import discord
from app.core.licensing import verify_license_signature

async def activate_license(bot, interaction: discord.Interaction, code: str, guild_id: int | None = None):
    target_guild_id = int(guild_id or interaction.guild_id or 0)
    if not target_guild_id:
        return False, '❌ This activation link is missing its server context. Ask an administrator to generate a new license.'
    code = code.upper().strip()
    r = bot.db.one('SELECT * FROM licenses WHERE code=? AND guild_id=?', (code, target_guild_id))
    if not r: return False, '❌ This license is not registered for this server.'
    if not verify_license_signature(code, r['signature_hmac']): return False, '❌ Invalid or forged license signature.'
    ent = bot.db.one("SELECT * FROM entitlements WHERE id=? AND guild_id=? AND user_id=?", (r['entitlement_id'], target_guild_id, interaction.user.id)) if r['entitlement_id'] else None
    if not ent or ent['status'] != 'active': return False, '❌ The access entitlement for this license is not active.'
    if ent['expires_at'] and datetime.fromisoformat(ent['expires_at']) <= datetime.now(timezone.utc): return False, '❌ The access entitlement for this license has expired.'
    if r['status'] != 'active': return False, f'❌ This license is {r["status"]}.'
    if r['expires_at']:
        try:
            if datetime.fromisoformat(r['expires_at']) < datetime.now(timezone.utc):
                bot.db.execute("UPDATE licenses SET status='expired' WHERE code=?", (code,))
                return False, '❌ Your license has expired.'
        except ValueError:
            return False, '❌ This license has an invalid expiration value. Contact an administrator.'
    assigned = r['assigned_user_id'] if 'assigned_user_id' in r.keys() else None
    if assigned not in (None, interaction.user.id): return False, '❌ This license was issued to another Discord account.'
    if r['user_id'] not in (None, interaction.user.id): return False, '❌ This license is already bound to another Discord account.'
    # Atomic bind + activation-limit enforcement prevents concurrent double activation.
    with bot.db.connect() as c:
        cur=c.execute('''UPDATE licenses SET user_id=?, activations=activations+1
                         WHERE code=? AND guild_id=? AND user_id IS NULL AND activations < max_activations''',
                      (interaction.user.id, code, target_guild_id))
        if cur.rowcount == 0:
            current=c.execute('SELECT user_id,activations,max_activations FROM licenses WHERE code=? AND guild_id=?',(code,target_guild_id)).fetchone()
            if not current or current['user_id'] not in (None, interaction.user.id): return False, '❌ This license is already bound to another Discord account.'
            if current['user_id'] is None: return False, '❌ This license has reached its activation limit.'
    guild = bot.get_guild(target_guild_id)
    role_note = ''
    if guild:
        s = bot.db.guild(target_guild_id)
        role = guild.get_role(s['member_role_id']) if s.get('member_role_id') else None
        member = guild.get_member(interaction.user.id)
        if member is None:
            try: member = await guild.fetch_member(interaction.user.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException): member = None
        if role and member:
            try: await member.add_roles(role, reason='420Vault license activation')
            except discord.Forbidden: role_note = '\n⚠️ Activated, but I could not assign the licensed role. An admin should check my role permissions.'
    return True, '✅ License activated. 420VaultBot is now unlocked for your account.' + role_note

class LicenseModal(discord.ui.Modal, title='🔓 Activate 420Vault License'):
    license_code = discord.ui.TextInput(label='License Code', placeholder='420V-XXXX-XXXX-XXXX', required=True, min_length=19, max_length=19)
    def __init__(self, bot, guild_id: int | None = None, prefill: str | None = None):
        super().__init__(); self.bot = bot; self.guild_id = guild_id
        if prefill: self.license_code.default = prefill
    async def on_submit(self, i):
        ok, msg = await activate_license(self.bot, i, str(self.license_code), self.guild_id)
        await i.response.send_message(msg, ephemeral=bool(i.guild_id))

class LicenseView(discord.ui.View):
    def __init__(self, bot): super().__init__(timeout=None); self.bot = bot
    @discord.ui.button(label='Enter License', emoji='🔓', style=discord.ButtonStyle.green, custom_id='420vault:persistent_license_button')
    async def enter(self, i, b):
        r = self.bot.db.one("SELECT 1 FROM licenses WHERE guild_id=? AND user_id=? AND status='active' LIMIT 1", (i.guild_id, i.user.id))
        if r: return await i.response.send_message('✅ You are already unlocked.', ephemeral=True)
        await i.response.send_modal(LicenseModal(self.bot, i.guild_id))

class DMLicenseView(discord.ui.View):
    """Persistent per-license DM activation button. Re-registered at startup."""
    def __init__(self, bot, guild_id: int, code: str):
        super().__init__(timeout=None)
        self.bot = bot; self.guild_id = int(guild_id); self.code = code
        # Stable custom_id lets discord.py reconnect this button after a restart.
        import hashlib
        cid = hashlib.sha256(f'{self.guild_id}:{self.code}'.encode()).hexdigest()[:24]
        button = discord.ui.Button(label='Activate License', emoji='🔑', style=discord.ButtonStyle.green, custom_id=f'420vault:dmactivate:{cid}')
        button.callback = self.activate
        self.add_item(button)
    async def activate(self, i):
        if i.guild_id is not None:
            return await i.response.send_message('Use this activation button from the DM where your license was delivered.', ephemeral=True)
        r = self.bot.db.one('SELECT user_id,status,assigned_user_id FROM licenses WHERE code=? AND guild_id=?', (self.code, self.guild_id))
        if not r:
            return await i.response.send_message('❌ This license no longer exists.')
        if r['assigned_user_id'] not in (None, i.user.id):
            return await i.response.send_message('❌ This license was issued to another Discord account.')
        if r['user_id'] == i.user.id and r['status'] == 'active':
            return await i.response.send_message('✅ This license is already activated on your account.')
        await i.response.send_modal(LicenseModal(self.bot, self.guild_id, self.code))

def license_embed():
    return discord.Embed(title='🔐 420VaultBot Locked', description='Click **Enter License** below to activate your 420Vault license and unlock the bot.\n\nIf you do not have a license, contact an administrator.', color=discord.Color.red())
