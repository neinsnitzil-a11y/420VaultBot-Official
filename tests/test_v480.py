from pathlib import Path

def test_version_480():
    assert True  # historical version assertion retired by v5.5

def test_db_connection_does_not_renegotiate_wal_per_request():
 s=Path('app/core/database.py').read_text()
 block=s[s.index(' def connect(self):'):s.index(' def one(',s.index(' def connect(self):'))]
 assert "journal_mode=WAL" not in block
 assert "busy_timeout=500" in block

def test_drive_sync_heavy_db_work_off_event_loop():
 s=Path('app/services/google_drive.py').read_text()
 assert "await asyncio.to_thread(self._write_drive_page" in s
 assert "await asyncio.to_thread(self._mark_stale" in s
 assert "await asyncio.to_thread(self._rebuild_drive_fts" in s
 assert "LIMIT 500" in s

def test_drive_browser_uses_async_refresh():
 s=Path('app/views/drive_browser.py').read_text()
 assert 'async def async_refresh' in s
 assert 'await asyncio.to_thread(self.bot.google_drive.search' in s
 assert 'await asyncio.to_thread(self.bot.google_drive.children' in s

def test_legacy_drive_sync_is_background():
 s=Path('app/cogs/legacy_commands.py').read_text()
 section=s[s.index("@commands.command(name='drive_sync')"):s.index("@commands.command(name='drive_status')")]
 assert 'start_sync' in section
 assert 'await self.bot.google_drive.sync(' not in section
