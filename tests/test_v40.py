from pathlib import Path

def test_version():
    from app.version import VERSION
    assert VERSION=='4.0.0'

def test_v4_bootstrap_roles_and_gate():
    s=Path('app/services/server_bootstrap.py').read_text(encoding='utf-8')
    for x in ('Verified','Unverified','Subscribed','Beta Tester','Vault Overseer'):
        assert x in s
    assert 'apply_onboarding_gate' in s
    assert 'view_channel=False' in s
    assert 'view_channel=True' in s

def test_join_routes_to_terms():
    s=Path('app/bot.py').read_text(encoding='utf-8')
    assert 'Open Terms & Verify' in s
    assert 'discord.com/channels/' in s
    assert "require_admin=True" in s
