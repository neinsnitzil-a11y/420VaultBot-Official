from pathlib import Path

def test_drive_admin_gui_present():
    s=Path('app/views/admin.py').read_text(encoding='utf-8')
    assert "('drive','Google Drive','☁️')" in s
    for action in ('drive_config','drive_test','drive_sync','drive_status','drive_disconnect'):
        assert action in s
    assert 'DriveRootModal' in s

def test_drive_config_command_gui_fallback():
    s=Path('app/cogs/legacy_commands.py').read_text(encoding='utf-8')
    assert "folder:str=''" in s
    assert "AdminView(self.bot,ctx.guild.id,'drive')" in s
