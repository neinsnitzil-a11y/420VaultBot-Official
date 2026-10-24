import tempfile
from pathlib import Path

from app.core.database import Database
from app.services.auth import AuthService
from app.services.user_profiles import UserProfileService


class DummySubs:
    def active_for(self,*a,**k): return None
    def entitlement_for(self,*a,**k): return None


class DummyBot:
    pass


def make_bot(tmp_path):
    bot=DummyBot(); bot.db=Database(tmp_path/'test.db'); bot.subscriptions=DummySubs()
    bot.auth=AuthService(bot); bot.profiles=UserProfileService(bot)
    return bot


def seed_account(bot,gid=1,uid=2):
    bot.auth.register(gid,uid,'tester','tester@example.com','ValidPassword123')
    bot.db.execute('UPDATE auth_accounts SET email_verified=1,totp_enabled=1,totp_secret_enc=?,totp_recovery_hashes=? WHERE guild_id=? AND discord_user_id=?',('dummy','[]',gid,uid))
    bot.auth.create_session(gid,uid)
    bot.auth.create_challenge(gid,uid)
    bot.auth.issue_email_token(gid,uid,'reset_password',900)
    bot.profiles.update_main(gid,uid,display_name='Public Tester',bio='hello')
    bot.profiles.set_public(gid,uid,True)


def test_delete_profile_preserves_account_and_access_tables(tmp_path):
    bot=make_bot(tmp_path); seed_account(bot)
    gid,uid=1,2
    bot.db.execute("INSERT INTO entitlements(guild_id,user_id,source,status,starts_at) VALUES(?,?,?,'active',CURRENT_TIMESTAMP)",(gid,uid,'admin'))
    assert bot.profiles.delete_profile_data(gid,uid) is True
    assert bot.profiles.get(gid,uid) is None
    assert bot.auth.account(gid,uid) is not None
    assert bot.db.one('SELECT * FROM entitlements WHERE guild_id=? AND user_id=?',(gid,uid)) is not None


def test_reset_test_account_removes_auth_profile_only(tmp_path):
    bot=make_bot(tmp_path); seed_account(bot)
    gid,uid=1,2
    bot.db.execute("INSERT INTO entitlements(guild_id,user_id,source,status,starts_at) VALUES(?,?,?,'active',CURRENT_TIMESTAMP)",(gid,uid,'admin'))
    bot.db.execute("INSERT INTO tos_acceptance(guild_id,user_id,tos_version,quiz_score) VALUES(?,?,?,?)",(gid,uid,'v1',100))
    assert bot.auth.reset_test_account(gid,uid) is True
    assert bot.auth.account(gid,uid) is None
    assert bot.db.one('SELECT * FROM user_profiles WHERE guild_id=? AND user_id=?',(gid,uid)) is None
    assert bot.db.one('SELECT * FROM auth_sessions WHERE guild_id=? AND user_id=?',(gid,uid)) is None
    assert bot.db.one('SELECT * FROM auth_challenges WHERE guild_id=? AND user_id=?',(gid,uid)) is None
    assert bot.db.one('SELECT * FROM auth_tokens WHERE guild_id=? AND user_id=?',(gid,uid)) is None
    assert bot.db.one('SELECT * FROM entitlements WHERE guild_id=? AND user_id=?',(gid,uid)) is not None
    assert bot.db.one('SELECT * FROM tos_acceptance WHERE guild_id=? AND user_id=?',(gid,uid)) is not None


def test_reset_allows_same_email_and_username_to_register_again(tmp_path):
    bot=make_bot(tmp_path); seed_account(bot)
    assert bot.auth.reset_test_account(1,2) is True
    bot.auth.register(1,2,'tester','tester@example.com','ValidPassword123')
    assert bot.auth.account(1,2) is not None


def test_ui_contains_confirmation_gates():
    root=Path(__file__).resolve().parents[1]
    profile=(root/'app/views/user_profile.py').read_text(encoding='utf-8')
    auth=(root/'app/views/auth_native.py').read_text(encoding='utf-8')
    assert 'DELETE PROFILE' in profile and 'Delete Profile Data' in profile
    assert 'RESET ACCOUNT' in auth and 'Reset Test Account' in auth
