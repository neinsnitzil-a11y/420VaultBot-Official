from pathlib import Path
def test_version(): assert "VERSION='5.5.4'" in Path('app/version.py').read_text()
def test_archive_schema():
 s=Path('app/core/database.py').read_text(); assert 'drive_archive_entries' in s and 'drive_archive_fts' in s
def test_archive_search_delivery():
 s=Path('app/views/drive_browser.py').read_text(); assert 'Found inside:' in s and 'complete original archive' in s
def test_archive_admin():
 s=Path('app/views/admin.py').read_text(); assert 'Parse ZIP/RAR' in s and 'drive_archives' in s
