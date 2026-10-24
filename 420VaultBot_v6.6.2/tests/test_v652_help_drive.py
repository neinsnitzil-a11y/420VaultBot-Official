import re, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CMD=(ROOT/'app/views/command_center.py').read_text()
LEG=(ROOT/'app/cogs/legacy_commands.py').read_text()
DRV=(ROOT/'app/views/drive_browser.py').read_text()

class V652HelpDriveTests(unittest.TestCase):
 def test_all_prefix_commands_have_button_specs(self):
  commands=set()
  for p in (ROOT/'app').rglob('*.py'):
   for line in p.read_text(encoding='utf-8',errors='ignore').splitlines():
    line=line.strip()
    if line.startswith('@commands.command(name='):
     q=line.split('name=',1)[1].lstrip()
     if q and q[0] in "'\"":
      commands.add(q[1:].split(q[0],1)[0])
  specs=set(re.findall(r"CommandSpec\('([^']+)'",CMD))
  self.assertEqual(commands,specs)
 def test_user_help_does_not_render_admin_categories(self):
  self.assertIn("_category_keys(self.include_admin)",CMD)
  self.assertIn("if include_admin or not meta[2]",CMD)
  self.assertIn("UserHelpHomeView(ctx.author.id,admin_requester)",LEG)
 def test_admin_commands_are_separate_private_hub(self):
  self.assertIn('Open Admin Command Center',CMD)
  self.assertIn('ephemeral=True',CMD.split('class OpenAdminHelpButton',1)[1])
  self.assertIn('Administrator-only categories',CMD)
 def test_drive_interaction_check_is_fast(self):
  block=DRV.split('async def interaction_check(self,i):',1)[1].split('async def ensure_access',1)[0]
  self.assertNotIn('session_active',block)
  self.assertNotIn('check_access',block)
 def test_drive_select_defers_before_access_and_db(self):
  block=DRV.split('class DriveSelect',1)[1].split('class DriveBrowserView',1)[0]
  self.assertLess(block.index('response.defer'),block.index('ensure_access'))
 def test_drive_nav_defers_before_access(self):
  for marker in ['async def prev','async def next','async def up']:
   block=DRV.split(marker,1)[1].split('@discord.ui.button',1)[0] if '@discord.ui.button' in DRV.split(marker,1)[1] else DRV.split(marker,1)[1]
   self.assertLess(block.index('response.defer'),block.index('ensure_access'))
 def test_version(self):
  self.assertEqual((ROOT/'VERSION').read_text().strip(),'6.5.5')

if __name__=='__main__':unittest.main()
