from dataclasses import dataclass
from datetime import datetime, timezone
from app.core.security import is_admin_member

@dataclass(frozen=True)
class AccessState:
    allowed: bool
    reason: str
    paid: bool=False
    beta: bool=False
    admin: bool=False
    verified: bool=False

def _has_role(member, role_id, fallback=None):
    # Role names are deliberately ignored; each guild stores its own Discord role IDs.
    return bool(role_id) and any(r.id==int(role_id) for r in getattr(member,'roles',[]))

def check_access(bot, guild, member, *, require_admin=False):
    if not guild or not member:return AccessState(False,'guild_required')
    s=bot.db.guild(guild.id)
    admin=is_admin_member(member,s)
    if require_admin:return AccessState(admin,'admin' if admin else 'admin_required',admin=admin)
    # Server administrators and configured admin roles bypass the TOS gate.
    # This keeps management commands usable even before onboarding is configured.
    if admin:return AccessState(True,'admin',admin=True,verified=True)
    from app.views.tos import accepted
    # TOS verification uses the guild's configured role ID; role names are not interpreted.
    tos_role=_has_role(member,s.get('verified_role_id'))
    verified=(not s.get('tos_enabled',1)) or accepted(bot.db,guild.id,member.id) or tos_role
    if not verified:return AccessState(False,'tos_required',admin=False,verified=False)
    beta=_has_role(member,s.get('beta_role_id'))
    # Beta Tester bypasses paid licensing only; TOS remains mandatory.
    if beta:return AccessState(True,'beta_tester',beta=True,verified=True)
    # Respect the server's existing paid-member role as an authoritative access role.
    paid_role=_has_role(member,s.get('subscribed_role_id'))
    if paid_role:return AccessState(True,'paid_member_role',paid=True,verified=True)
    if not s.get('licensing_enabled',1):return AccessState(True,'licensing_disabled',verified=True)
    ent=bot.subscriptions.entitlement_for(guild.id,member.id)
    if not ent:return AccessState(False,'entitlement_required',verified=True)
    lic=bot.db.one("SELECT 1 FROM licenses WHERE guild_id=? AND user_id=? AND entitlement_id=? AND status='active' LIMIT 1",(guild.id,member.id,ent['id']))
    if not lic:return AccessState(False,'license_activation_required',verified=True)
    sub=bot.subscriptions.active_for(guild.id,member.id)
    return AccessState(True,'licensed',paid=bool(sub),verified=True)
