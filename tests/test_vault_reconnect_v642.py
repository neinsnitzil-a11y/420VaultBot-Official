import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.services.indexer import VaultIndexer
from app.services.vault_paths import resolve_vault_item,repair_vault_path

class FakeDB:
    def __init__(self, path): self.path=path
    def connect(self):
        c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row;return c
    def execute(self,sql,args):
        with self.connect() as c: c.execute(sql,args)

class VaultReconnectTests(unittest.TestCase):
    def test_unchanged_file_becomes_available_again(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'vault';root.mkdir();(root/'test.wav').write_bytes(b'123')
            db=FakeDB(str(Path(temp)/'db.sqlite'))
            with db.connect() as c:
                c.executescript("CREATE TABLE vault_scan_state(guild_id INTEGER PRIMARY KEY,last_status TEXT,last_error TEXT,last_scan TEXT); CREATE TABLE vault_folders(id INTEGER PRIMARY KEY,guild_id INTEGER,name TEXT,relative_path TEXT,full_path TEXT,modified_at REAL,child_count INTEGER,available INTEGER,UNIQUE(guild_id,relative_path));CREATE TABLE vault_files(id INTEGER PRIMARY KEY,guild_id INTEGER,filename TEXT,full_path TEXT,folder TEXT,extension TEXT,category TEXT,file_size INTEGER,modified_at REAL,available INTEGER,UNIQUE(guild_id,full_path));CREATE VIRTUAL TABLE vault_fts USING fts5(kind,item_id,guild_id,name,path,extension,category);")
            x=VaultIndexer(db);x.scan(1,str(root));db.execute('UPDATE vault_files SET available=0 WHERE guild_id=?',(1,));x.scan(1,str(root));
            with db.connect() as c:
                self.assertEqual(c.execute('SELECT available FROM vault_files').fetchone()[0],1)
    def test_relocated_file_only_inside_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'new';(root/'Kits').mkdir(parents=True);(root/'Kits'/'kick.wav').write_bytes(b'kick')
            rec={'id':4,'full_path':'Z:/old/Kits/kick.wav','folder':'Kits','filename':'kick.wav'}
            path,reason,moved=resolve_vault_item(str(root),rec,'file')
            self.assertEqual(path, (root/'Kits'/'kick.wav').resolve());self.assertTrue(moved)
            rec['folder']='../../outside';path,reason,moved=resolve_vault_item(str(root),rec,'file')
            self.assertIsNone(path)
    def test_hidden_metadata_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'vault';root.mkdir();(root/'.DS_Store').write_bytes(b'x');(root/'test.wav').write_bytes(b'x')
            db=FakeDB(str(Path(temp)/'db.sqlite'))
            with db.connect() as c:c.executescript("CREATE TABLE vault_scan_state(guild_id INTEGER PRIMARY KEY,last_status TEXT,last_error TEXT,last_scan TEXT); CREATE TABLE vault_folders(id INTEGER PRIMARY KEY,guild_id INTEGER,name TEXT,relative_path TEXT,full_path TEXT,modified_at REAL,child_count INTEGER,available INTEGER,UNIQUE(guild_id,relative_path));CREATE TABLE vault_files(id INTEGER PRIMARY KEY,guild_id INTEGER,filename TEXT,full_path TEXT,folder TEXT,extension TEXT,category TEXT,file_size INTEGER,modified_at REAL,available INTEGER,UNIQUE(guild_id,full_path));CREATE VIRTUAL TABLE vault_fts USING fts5(kind,item_id,guild_id,name,path,extension,category);")
            VaultIndexer(db).scan(1,str(root))
            with db.connect() as c:self.assertEqual([r[0] for r in c.execute('SELECT filename FROM vault_files')],['test.wav'])

if __name__=='__main__':unittest.main()
