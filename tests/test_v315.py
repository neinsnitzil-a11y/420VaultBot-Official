from pathlib import Path

def test_bootstrap_has_terms():
    s=Path('app/services/server_bootstrap.py').read_text()
    assert "'terms'" in s
    assert "changes['tos_channel_id']" in s
    assert 'publish_tos' in s

def test_admin_tos_bypass_order():
    s=Path('app/services/access.py').read_text()
    assert s.index("if admin:return AccessState(True,'admin'") < s.index('from app.views.tos import accepted')

def test_version():
    from app.version import VERSION
    assert VERSION=='3.15.0'
