import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SETUP=(ROOT/'app/views/setup.py').read_text()
class V651SetupRegressionTests(unittest.TestCase):
 def test_no_reserved_component_parent_assignment(self):
  self.assertNotIn('self.parent=',SETUP)
  self.assertNotIn('self.parent.',SETUP)
 def test_channel_route_defers_before_db_work(self):
  block=SETUP.split('class UtilityChannelSelect',1)[1].split('class RoleMappingSelect',1)[0]
  self.assertLess(block.index('i.response.defer'),block.index('db.set_channels'))
  self.assertIn('i.followup.send',block)
 def test_role_route_defers_before_db_work(self):
  block=SETUP.split('class RoleMappingSelect',1)[1].split('class SetupRoleFieldSelect',1)[0]
  self.assertLess(block.index('i.response.defer'),block.index('db.set_guild'))
  self.assertIn('i.followup.send',block)
 def test_advanced_embed_is_rendered_in_embed_method(self):
  rebuild=SETUP.split('def rebuild(self):',1)[1].split('def missing(self,guild):',1)[0]
  self.assertNotIn("e.description='Finish the detailed configuration",rebuild)
  embed=SETUP.split('def embed(self,guild):',1)[1]
  self.assertIn("elif self.section=='advanced':",embed)
 def test_version(self):
  self.assertEqual((ROOT/'VERSION').read_text().strip(),'6.5.5')
if __name__=='__main__':unittest.main()
