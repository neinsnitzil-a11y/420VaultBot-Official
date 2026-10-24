from pathlib import Path
import tempfile
from app.core.database import Database
from app.services.indexer import VaultIndexer

def test_multi_root_indexes_without_cross_offline():
    with tempfile.TemporaryDirectory() as td:
        t=Path(td);a=t/'A';b=t/'B';a.mkdir();b.mkdir();(a/'kick.wav').write_bytes(b'a');(b/'snare.wav').write_bytes(b'b')
        db=Database(t/'db.sqlite3');db.add_vault_root(1,str(a),'A');db.add_vault_root(1,str(b),'B')
        ix=VaultIndexer(db);ix.scan(1,str(a));ix.scan(1,str(b))
        rows=db.all('SELECT filename,available,source_root FROM vault_files WHERE guild_id=1 ORDER BY filename')
        assert len(rows)==2 and all(r['available']==1 for r in rows)
        (a/'kick.wav').unlink();ix.scan(1,str(a))
        rows={r['filename']:r for r in db.all('SELECT filename,available FROM vault_files WHERE guild_id=1')}
        assert rows['kick.wav']['available']==0 and rows['snare.wav']['available']==1
