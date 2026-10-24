"""Configurable command routing for 420VaultBot.

v6.5.3 removes deployment-specific channel IDs as the primary policy and lets
420_setup map each utility to one or more Discord channels. Existing installs
remain compatible: when a utility has not been mapped yet, the legacy/general
``search`` channel list is used as the fallback for user-facing commands.
Administrators may additionally use configured ``admin`` channels and the
portable bot-testing channel.
"""

# Legacy deployment IDs remain only as a compatibility fallback.
AUDIO_VAULT_CATEGORY_ID = 1466503186675400927
ADMIN_BOT_TESTING_CHANNEL_ID = 1466319233452347463
USER_COMMAND_CHANNEL_IDS = (
    1469773544312537088,1467329213152366810,1466517009012621636,
    1466517082303893596,1466517148439679086,1466517190164611072,
    1466517226612986001,1466517121084162201,1466516757375090814,
    1466516895191662705,1466516679159976122,1466516560008183890,
    1466503803972096185,1466503495841616055,1466503663773286523,
)

# Command -> setup routing purpose. Commands absent here fall back to ``search``.
COMMAND_PURPOSE = {
    'auth':'account','logout':'account','profile':'profile','profile_search':'profile',
    'help':'help','user_manual':'help','features':'help','sources':'help','status':'help','version':'help',
    'tos':'tos',
    'search':'links','search_site':'links','sendlink':'links',
    'vault_search':'vault','vault_search_type':'vault','vault_search_size':'vault',
    'vault_search_terms':'vault','vault_random':'vault','vault_stats':'vault',
    'vault_list':'vault','download_vault':'vault',
    'drive_search':'drive','server_search':'remote',
    'subscribe':'subscription','subscription':'subscription',
    # Administrator commands are intentionally grouped into the admin zone.
    'setup':'admin','admin':'admin','admin_manual':'admin','diagnostics':'admin',
    'showchannels':'admin','lockdown':'admin','unlock':'admin','exportserver':'admin',
    'vault_path':'admin','reindex_vault':'admin','admin_delete_vault_index':'admin',
    'drive_config':'admin','drive_sync':'admin','drive_status':'admin',
    'importlinks':'admin','reloadlinks':'admin','addlicense':'admin',
    'approvepayment':'admin','resendlicense':'admin','revokelicense':'admin',
    'showlicense':'admin','listlicenses':'admin','resetuserlicenses':'admin',
}


def _audio_vault_children(guild):
    if not guild:return []
    category=guild.get_channel(AUDIO_VAULT_CATEGORY_ID)
    if category is not None and getattr(category,'channels',None) is not None:
        ids=[int(ch.id) for ch in category.channels if hasattr(ch,'send')]
        if ids:return ids
    return [cid for cid in USER_COMMAND_CHANNEL_IDS if guild.get_channel(cid) is not None]


def admin_testing_channel(guild):
    if not guild:return None
    ch=guild.get_channel(ADMIN_BOT_TESTING_CHANNEL_ID)
    if ch is not None:return ch
    for candidate in getattr(guild,'text_channels',()):
        if str(getattr(candidate,'name','')).lower() in {'🧪-bot-testing','bot-testing'}:return candidate
    return None


def _configured(db,guild_id,purpose):
    if db is None:return []
    try:return list(db.channels(guild_id,purpose))
    except Exception:return []


def allowed_command_channel_ids(guild,db=None,admin=False,purpose=None):
    """Return allowed channels for a command/utility.

    ``purpose`` is configured by 420_setup. If a specific route has not been
    configured, user utilities fall back to the general ``search`` route and
    finally to the legacy AUDIO VAULT deployment for backwards compatibility.
    Admins also receive the configured admin route and bot-testing channel.
    """
    if guild is None:return []
    purpose=(purpose or 'search').strip().lower()
    ids=_configured(db,guild.id,purpose)
    if not ids and purpose not in {'admin','tos','account','license','tickets','logs'}:
        ids=_configured(db,guild.id,'search')
    if not ids and purpose not in {'admin','tos','account','license','tickets','logs'}:
        ids=_audio_vault_children(guild)
    if admin:
        ids += _configured(db,guild.id,'admin')
        test=admin_testing_channel(guild)
        if test is not None:ids.append(int(test.id))
    return list(dict.fromkeys(int(x) for x in ids))


def command_channel_allowed(guild,channel,db=None,admin=False,purpose=None):
    if guild is None:return True
    if channel is None:return False
    return int(channel.id) in allowed_command_channel_ids(guild,db=db,admin=admin,purpose=purpose)


def command_purpose(command_name):
    return COMMAND_PURPOSE.get(str(command_name or '').lower(),'search')
