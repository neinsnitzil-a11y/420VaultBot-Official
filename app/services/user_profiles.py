from __future__ import annotations

import re
import time
from urllib.parse import urlparse


def _clean(value, limit):
    return ' '.join(str(value or '').strip().split())[:limit]


def _bio(value, limit=1000):
    return str(value or '').strip().replace('\x00', '')[:limit]


def _website(value):
    value = str(value or '').strip()[:300]
    if not value:
        return ''
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', value) and not re.match(r'^https?://', value, re.I):
        raise ValueError('Website must use http:// or https://.')
    if not re.match(r'^https?://', value, re.I):
        value = 'https://' + value
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('Website must be a valid http/https URL.')
    return value


class UserProfileService:
    """Editable account profiles. Security/account truth remains in canonical auth/license tables."""
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db

    def ensure(self, gid: int, uid: int):
        account = self.db.one('SELECT id,created_at FROM auth_accounts WHERE guild_id=? AND discord_user_id=?', (gid, uid))
        if not account:
            return None
        now = int(time.time())
        self.db.execute(
            'INSERT OR IGNORE INTO user_profiles(guild_id,user_id,created_at,updated_at) VALUES(?,?,?,?)',
            (gid, uid, int(account['created_at'] or now), now),
        )
        return self.get(gid, uid)

    def get(self, gid: int, uid: int):
        row = self.db.one('SELECT * FROM user_profiles WHERE guild_id=? AND user_id=?', (gid, uid))
        return dict(row) if row else None

    def update_main(self, gid: int, uid: int, *, display_name='', creator_name='', bio='', website='', genres=''):
        if not self.ensure(gid, uid):
            raise ValueError('Create a 420Vault account first.')
        vals = {
            'display_name': _clean(display_name, 80),
            'creator_name': _clean(creator_name, 80),
            'bio': _bio(bio, 1000),
            'website': _website(website),
            'genres': _clean(genres, 250),
        }
        self.db.execute(
            'UPDATE user_profiles SET display_name=?,creator_name=?,bio=?,website=?,genres=?,updated_at=? WHERE guild_id=? AND user_id=?',
            (*vals.values(), int(time.time()), gid, uid),
        )
        self.db.audit(gid, uid, 'profile_updated', 'main profile fields updated')
        return self.get(gid, uid)

    def update_details(self, gid: int, uid: int, *, daw='', socials='', timezone='', interests=''):
        if not self.ensure(gid, uid):
            raise ValueError('Create a 420Vault account first.')
        self.db.execute(
            'UPDATE user_profiles SET daw=?,socials=?,timezone=?,interests=?,updated_at=? WHERE guild_id=? AND user_id=?',
            (_clean(daw, 150), _bio(socials, 500), _clean(timezone, 80), _clean(interests, 300), int(time.time()), gid, uid),
        )
        self.db.audit(gid, uid, 'profile_updated', 'profile details updated')
        return self.get(gid, uid)

    def set_public(self, gid: int, uid: int, public: bool):
        if not self.ensure(gid, uid):
            raise ValueError('Create a 420Vault account first.')
        self.db.execute('UPDATE user_profiles SET public_profile=?,updated_at=? WHERE guild_id=? AND user_id=?', (1 if public else 0, int(time.time()), gid, uid))
        self.db.audit(gid, uid, 'profile_visibility', 'public' if public else 'private')
        return self.get(gid, uid)

    def search_public(self, gid: int, query: str = '', limit: int = 150):
        """Only opt-in public profiles in the current Discord guild; no sensitive columns."""
        query = ' '.join(str(query or '').strip().split())[:100]
        limit = max(1, min(int(limit), 150))
        if query:
            # Escape SQL LIKE metacharacters so a user's search is literal.
            escaped = query.lower().replace('~', '~~').replace('%', '~%').replace('_', '~_')
            pattern = f'%{escaped}%'
            rows = self.db.all("""SELECT p.user_id, p.display_name, p.creator_name, p.genres,
                                     p.daw, a.username
                              FROM user_profiles p
                              JOIN auth_accounts a
                                ON a.guild_id=p.guild_id AND a.discord_user_id=p.user_id
                              WHERE p.guild_id=? AND p.public_profile=1
                                AND (LOWER(p.display_name) LIKE ? ESCAPE '~'
                                 OR LOWER(p.creator_name) LIKE ? ESCAPE '~'
                                 OR LOWER(p.genres) LIKE ? ESCAPE '~'
                                 OR LOWER(p.daw) LIKE ? ESCAPE '~'
                                 OR LOWER(a.username) LIKE ? ESCAPE '~')
                              ORDER BY p.updated_at DESC, p.user_id LIMIT ?""",
                              (gid, pattern, pattern, pattern, pattern, pattern, limit))
        else:
            rows = self.db.all("""SELECT p.user_id, p.display_name, p.creator_name, p.genres,
                                     p.daw, a.username
                              FROM user_profiles p
                              JOIN auth_accounts a
                                ON a.guild_id=p.guild_id AND a.discord_user_id=p.user_id
                              WHERE p.guild_id=? AND p.public_profile=1
                              ORDER BY p.updated_at DESC, p.user_id LIMIT ?""", (gid, limit))
        return [dict(row) for row in rows]

    def summary(self, gid: int, uid: int):
        profile = self.ensure(gid, uid)
        account = self.db.one('SELECT username,email_verified,totp_enabled,created_at FROM auth_accounts WHERE guild_id=? AND discord_user_id=?', (gid, uid))
        if not account:
            return None
        sub = self.bot.subscriptions.active_for(gid, uid)
        entitlement = self.bot.subscriptions.entitlement_for(gid, uid)
        license_row = self.db.one("SELECT code,status,expires_at FROM licenses WHERE guild_id=? AND assigned_user_id=? ORDER BY created_at DESC LIMIT 1", (gid, uid))
        return {
            'profile': profile or {},
            'account': dict(account),
            'subscription': dict(sub) if sub else None,
            'entitlement': dict(entitlement) if entitlement else None,
            'license': dict(license_row) if license_row else None,
        }
