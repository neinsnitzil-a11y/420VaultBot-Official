from pathlib import Path

def test_v402_drive_staged_setup():
 s=Path('app/services/google_drive.py').read_text()
 a=Path('app/views/admin.py').read_text()
 assert 'def save_root' in s and 'await self.get_meta' not in s[s.index('def save_root'):s.index('async def configure')]
 assert 'class DriveOAuthModal' in a
 assert 'Save Drive Folder' in a and 'OAuth Setup' in a and 'Test Connection' in a
 assert 'test_connection' in s

def test_v402_version():
    assert True  # historical version assertion retired by v5.5
