import tempfile,unittest,sqlite3,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('updater_safe',ROOT/'app/services/updater.py');u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
class ReliabilityTests(unittest.TestCase):
 def test_backup_of_live_wal_database(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);data=root/'data';data.mkdir();db=data/'live.db'
   conn=sqlite3.connect(db);conn.execute('PRAGMA journal_mode=WAL');conn.execute('CREATE TABLE state (value TEXT)');conn.execute('INSERT INTO state VALUES ("license survives")');conn.commit()
   backup=u.create_backup(root)
   self.assertTrue(u.verify_backup(backup)[0]);self.assertEqual(sqlite3.connect(backup/'data/live.db').execute('SELECT value FROM state').fetchone()[0],'license survives')
   conn.close()
 def test_backup_names_do_not_collide(self):
  with tempfile.TemporaryDirectory() as tmp:
   first=u.create_backup(tmp);second=u.create_backup(tmp);self.assertNotEqual(first,second)
 def test_manifest_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=u.create_backup(tmp);(p/'backup_manifest.json').write_text('{"files":[{"path":"../../outside","sha256":"a"}]}');self.assertFalse(u.verify_backup(p)[0])
 def test_defer_precedes_backup(self):
  source=(ROOT/'app/views/admin.py').read_text();start=source.index("if a=='update_backup':");end=source.index("if a=='update_backups':",start);section=source[start:end];self.assertLess(section.index('await i.response.defer'),section.index('create_backup,'));self.assertIn('i.followup.send',section)
 def test_dynamic_admin_footer(self):
  self.assertIn("f'420Vault v{VERSION} • Admin GUI'",(ROOT/'app/views/admin.py').read_text())
if __name__=='__main__':unittest.main()
