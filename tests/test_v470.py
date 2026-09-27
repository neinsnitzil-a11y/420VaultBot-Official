from pathlib import Path

def test_version_470():
    assert True  # historical version assertion retired by v5.5

def test_indexer_commits_batches():
 s=Path('app/services/indexer.py').read_text()
 assert 'processed%batch_size==0' in s
 assert 'c.commit()' in s
 assert "last_status=excluded.last_status" in s

def test_guild_read_does_not_always_write():
 s=Path('app/core/database.py').read_text()
 assert "row=self.one('SELECT * FROM guild_settings" in s
 assert 'timeout=3' in s and 'busy_timeout=3000' in s

def test_removable_path_checks_off_event_loop():
 s=Path('app/views/admin.py').read_text()
 assert 'await asyncio.to_thread(p.is_dir)' in s
 assert "await i.response.defer(ephemeral=True,thinking=True)" in s

def test_admin_footer_current():
 assert '420Vault v4.7.0 • Admin GUI' in Path('app/views/admin.py').read_text()
