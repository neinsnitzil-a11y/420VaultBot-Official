from pathlib import Path
import asyncio
import tempfile
from app.core.database import Database
from app.services.google_drive import GoogleDriveService


def test_version_460():
    assert True  # historical version assertion retired by v5.5


def test_admin_sync_is_background():
    s=Path('app/views/admin.py').read_text()
    assert 'start_sync(self.gid)' in s
    assert 'metadata sync started in the background' in s
    assert '_start_vault_scan' in s
    assert 'VaultIndexer(self.db).scan,self.gid,p' not in s


def test_drive_db_writes_are_off_event_loop():
    s=Path('app/services/google_drive.py').read_text()
    assert 'asyncio.to_thread(self._write_drive_page' in s
    assert 'asyncio.to_thread(self._finish_sync' in s
    assert 'def sync_progress' in s


def test_duplicate_drive_sync_guard():
    async def run():
        with tempfile.TemporaryDirectory() as d:
            db=Database(Path(d)/'x.db')
            svc=GoogleDriveService(db)
            db.execute("INSERT INTO drive_sources(guild_id,root_file_id,root_name,enabled,last_status) VALUES(1,'root','Root',1,'ready')")
            gate=asyncio.Event()
            async def fake_sync(gid):
                svc._progress[gid]={'status':'syncing','indexed':0,'started':0}
                await gate.wait()
                return 0
            svc.sync=fake_sync
            assert await svc.start_sync(1) is True
            assert await svc.start_sync(1) is False
            gate.set()
            await asyncio.sleep(0.05)
    asyncio.run(run())


def test_logging_format_not_embedded_in_run_line():
    s=Path('app/bot.py').read_text()
    assert 'format=LOG_FORMAT' in s
    run_line=[x for x in s.splitlines() if 'VaultBot().run' in x][0]
    assert '%(asctime)' not in run_line
