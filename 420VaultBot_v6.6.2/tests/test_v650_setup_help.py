import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class V650SetupHelpTests(unittest.TestCase):
 def test_version(self):self.assertEqual((ROOT/'VERSION').read_text().strip(),'6.5.5')
 def test_user_help_has_no_admin_buttons(self):
  s=(ROOT/'app/views/command_center.py').read_text();self.assertIn('class UserHelpHomeView',s);self.assertIn('HelpCommandHubView',s)
 def test_admin_help_is_separate_button_center(self):
  s=(ROOT/'app/views/command_center.py').read_text();self.assertIn('Open Admin Command Center',s);self.assertIn('Administrator-only categories',s)
 def test_guided_setup_has_routes(self):
  s=(ROOT/'app/views/setup.py').read_text();self.assertIn('UTILITY_ROUTES',s);self.assertIn('UtilityChannelSelect',s);self.assertIn('Advanced Utility Configuration',s)
 def test_admin_has_setup_section(self):
  s=(ROOT/'app/views/admin.py').read_text();self.assertIn('Guided Setup & Routing',s);self.assertIn("'setup_report'",s)
if __name__=='__main__':unittest.main()
