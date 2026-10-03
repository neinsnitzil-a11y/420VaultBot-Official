from pathlib import Path

def test_version_550():assert "VERSION='5.5.0'" in Path('app/version.py').read_text()
def test_manual_commands():
 s=Path('app/cogs/legacy_commands.py').read_text();assert "name='user_manual'" in s and "name='admin_manual'" in s
def test_persistent_vault_policy():
 s=Path('app/services/indexer.py').read_text();assert 'UPDATE vault_files SET available=0' in s;assert "DELETE FROM vault_files WHERE guild_id=?" not in s
def test_live_scraper_dashboard():
 s=Path('app/views/admin.py').read_text();assert '420Vault Live Web Scraper' in s and 'LIVE LINK STREAM' in s
def test_audio_preview():
 s=Path('app/views/vault_browser.py').read_text();assert 'Preview Audio' in s and 'ffmpeg' in s
def test_remote_servers():
 s=Path('app/core/database.py').read_text();assert 'remote_sources' in s and 'remote_items' in s
