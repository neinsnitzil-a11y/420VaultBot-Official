"""Canonical Discord command zones for the Keys of Sorrow deployment.

v6.2.4 rules:
- normal users: 420_ commands/buttons only inside text channels under AUDIO VAULT
- administrators: the same AUDIO VAULT channels plus #🧪-bot-testing

Other guilds keep using configured Search & Delivery channels for users. Admins in
other guilds may also use an exact channel named ``🧪-bot-testing`` or ``bot-testing``
when present, in addition to configured Search & Delivery channels.
"""

AUDIO_VAULT_CATEGORY_ID = 1466503186675400927
ADMIN_BOT_TESTING_CHANNEL_ID = 1466319233452347463

# Legacy IDs are retained as a fallback if Discord category metadata is unavailable.
USER_COMMAND_CHANNEL_IDS = (
    1469773544312537088,  # 420vaultbot-cheetheet-and-commands
    1467329213152366810,  # beats
    1466517009012621636,  # zenology-bank
    1466517082303893596,  # serum-1-and-2-banks
    1466517148439679086,  # portal-banks
    1466517190164611072,  # gross-beat-presets
    1466517226612986001,  # midi
    1466517121084162201,  # omnisphere-bank
    1466516757375090814,  # fx-sounds
    1466516895191662705,  # presets-banks
    1466516679159976122,  # loops
    1466516560008183890,  # one-shots
    1466503803972096185,  # drumkits-sounds
    1466503495841616055,  # cracked-plugins
    1466503663773286523,  # keygens
)


def _audio_vault_children(guild):
    if not guild:
        return []
    category = guild.get_channel(AUDIO_VAULT_CATEGORY_ID)
    if category is not None and getattr(category, 'channels', None) is not None:
        ids = [int(ch.id) for ch in category.channels if hasattr(ch, 'send')]
        if ids:
            return ids
    # Fallback for the target deployment if category resolution is unavailable.
    present = [cid for cid in USER_COMMAND_CHANNEL_IDS if guild.get_channel(cid) is not None]
    return present


def deployment_user_channels(guild):
    """Return AUDIO VAULT text channels for the target deployment, else []."""
    return _audio_vault_children(guild)


def admin_testing_channel(guild):
    if not guild:
        return None
    ch = guild.get_channel(ADMIN_BOT_TESTING_CHANNEL_ID)
    if ch is not None:
        return ch
    # Portable fallback for other guilds or a recreated channel.
    for candidate in getattr(guild, 'text_channels', ()):
        if str(getattr(candidate, 'name', '')).lower() in {'🧪-bot-testing', 'bot-testing'}:
            return candidate
    return None


def allowed_command_channel_ids(guild, db=None, admin=False):
    """Return channels in which a member may launch 420_ commands/buttons."""
    user_ids = deployment_user_channels(guild)
    if not user_ids and guild is not None and db is not None:
        user_ids = list(db.channels(guild.id, 'search'))
    ids = list(dict.fromkeys(int(x) for x in user_ids))
    if admin:
        test = admin_testing_channel(guild)
        if test is not None and int(test.id) not in ids:
            ids.append(int(test.id))
    return ids


def command_channel_allowed(guild, channel, db=None, admin=False):
    if guild is None:
        return True
    if channel is None:
        return False
    return int(channel.id) in allowed_command_channel_ids(guild, db=db, admin=admin)
