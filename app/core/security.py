import discord

def member_from(subject):
    """Return the Discord Member represented by a context/interaction/member."""
    if isinstance(subject, discord.Member):
        return subject
    return getattr(subject, 'user', None) or getattr(subject, 'author', None)

def is_admin_member(member, settings:dict)->bool:
    """Canonical 420Vault administrator/configured-admin-role decision."""
    if not isinstance(member, discord.Member): return False
    if member.guild_permissions.administrator: return True
    admin_id=settings.get('admin_role_id'); overseer_id=settings.get('overseer_role_id')
    for role in getattr(member,'roles',[]):
        if admin_id and role.id==admin_id: return True
        if overseer_id and role.id==overseer_id: return True
    return False

def is_admin(subject, settings:dict)->bool:
    # Backward-compatible wrapper used by cogs/views; all paths now share one implementation.
    return is_admin_member(member_from(subject), settings)
