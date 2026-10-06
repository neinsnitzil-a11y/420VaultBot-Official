import tempfile
from pathlib import Path
from app.core.database import Database
from app.services.search import SearchService
from app.services.indexer import VaultIndexer

def test_index_and_search():
 with tempfile.TemporaryDirectory() as td:
  root=Path(td);vault=root/'vault';vault.mkdir();(vault/'Serum Trap Bank.zip').write_bytes(b'abc')
  db=Database(root/'test.db');n,stale=VaultIndexer(db).rebuild(str(vault));assert n==1 and stale==0
  p=SearchService(db).search('serum trap');assert p.total==1 and p.items[0]['filename']=='Serum Trap Bank.zip'
