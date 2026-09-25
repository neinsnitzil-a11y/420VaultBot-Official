from pathlib import Path
from tempfile import TemporaryDirectory
from app.core.database import Database
from app.services.google_drive import folder_id

def test_drive_schema_and_isolation():
 with TemporaryDirectory() as td:
  db=Database(Path(td)/'x.db')
  db.execute("INSERT INTO drive_sources(guild_id,root_file_id,root_name) VALUES(1,'root1','One')")
  db.execute("INSERT INTO drive_sources(guild_id,root_file_id,root_name) VALUES(2,'root2','Two')")
  db.execute("INSERT INTO drive_items(guild_id,file_id,parent_id,name,mime_type,relative_path) VALUES(1,'f1','root1','Serum One','application/zip','Serum One')")
  db.execute("INSERT INTO drive_items(guild_id,file_id,parent_id,name,mime_type,relative_path) VALUES(2,'f2','root2','Private Two','application/zip','Private Two')")
  db.execute("INSERT INTO drive_fts(file_id,guild_id,name,path,mime_type) VALUES('f1',1,'Serum One','Serum One','application/zip')")
  db.execute("INSERT INTO drive_fts(file_id,guild_id,name,path,mime_type) VALUES('f2',2,'Private Two','Private Two','application/zip')")
  assert db.one("SELECT value FROM schema_meta WHERE key='schema_version'")['value']=='14'
  assert db.one('SELECT COUNT(*) n FROM drive_items WHERE guild_id=1')['n']==1
  assert db.one('SELECT COUNT(*) n FROM drive_items WHERE guild_id=2')['n']==1

def test_folder_id():
 assert folder_id('https://drive.google.com/drive/folders/abc_DEF-123?usp=sharing')=='abc_DEF-123'
 assert folder_id('abc_DEF-123')=='abc_DEF-123'
