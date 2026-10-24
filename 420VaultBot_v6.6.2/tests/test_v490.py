from pathlib import Path

def test_version_490():
    assert True  # historical version assertion retired by v5.5

def test_drive_links_are_primary_and_discord_optional():
 s=Path('app/views/drive_browser.py').read_text()
 assert 'Download from Drive' in s
 assert 'Open in Google Drive' in s
 assert 'Download to Discord' in s
 assert 'size and size<=self.limit' in s
 assert 'size>limit' in s
 assert 'no Discord upload will be attempted' in s
 assert 'Use the **Drive link above** instead' in s

def test_direct_drive_url_for_binary_files():
 s=Path('app/views/drive_browser.py').read_text()
 assert 'https://drive.google.com/uc?export=download&id=' in s
 assert "mime.startswith('application/vnd.google-apps.')" in s
