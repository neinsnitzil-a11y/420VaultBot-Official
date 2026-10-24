from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from app.core.database import Database


def test_core_writes_serialize_without_locked(tmp_path: Path):
    db=Database(tmp_path/'core.db')
    db.execute('INSERT OR IGNORE INTO guild_settings(guild_id) VALUES(?)',(1,))
    def write(i):
        db.execute('INSERT INTO audit_log(guild_id,user_id,action,details) VALUES(?,?,?,?)',(1,i,'test',str(i)))
        return i
    with ThreadPoolExecutor(max_workers=16) as ex:
        got=list(ex.map(write,range(200)))
    assert len(got)==200
    assert db.one('SELECT COUNT(*) n FROM audit_log')['n']==200


def test_vault_and_core_have_independent_writer_lanes(tmp_path: Path):
    db=Database(tmp_path/'core.db')
    db.execute('INSERT OR IGNORE INTO guild_settings(guild_id) VALUES(?)',(1,))
    # Both DBs can be written concurrently; they use independent locks/files.
    def core():
        for i in range(50):
            db.execute('INSERT INTO audit_log(guild_id,user_id,action,details) VALUES(?,?,?,?)',(1,i,'core','x'))
    def vault():
        for i in range(50):
            db.execute('INSERT OR IGNORE INTO vault_roots(guild_id,path,label,enabled) VALUES(?,?,?,1)',(1,f'/tmp/root{i}',f'r{i}'))
    with ThreadPoolExecutor(max_workers=2) as ex:
        list(ex.map(lambda f:f(),[core,vault]))
    assert db.one('SELECT COUNT(*) n FROM audit_log')['n']==50
    assert db.one('SELECT COUNT(*) n FROM vault_roots')['n']==50
