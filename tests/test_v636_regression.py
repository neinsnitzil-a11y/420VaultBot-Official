from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]
def test_version():
 assert (ROOT/'VERSION').read_text().strip()=='6.3.6'
 assert "VERSION='6.3.6'" in (ROOT/'app/version.py').read_text()
def test_guards():
 files={k:(ROOT/k).read_text() for k in ('app/views/command_center.py','app/views/auth_native.py','app/views/user_profile.py','app/services/user_profiles.py','app/cogs/legacy_commands.py','app/bot.py')}
 assert 'HelpCommandDirectoryView' in files['app/views/command_center.py']
 assert 'CommandCenterView' in files['app/views/command_center.py']
 assert 'public_profile' in files['app/services/user_profiles.py']
 assert 'Enable 2FA' in files['app/views/auth_native.py']
 assert 'Private welcome after successful verification' in files['app/views/auth_native.py']
 assert "@commands.command(name='help')" in files['app/cogs/legacy_commands.py']
 assert 'await self.ensure_command_panels(g.id)' in files['app/bot.py']
def test_syntax():
 for p in (ROOT/'app').rglob('*.py'):ast.parse(p.read_text(),filename=str(p))
