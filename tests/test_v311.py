from pathlib import Path
from tempfile import TemporaryDirectory
from app.core.database import Database

def test_schema_v11_and_rollback():
    with TemporaryDirectory() as d:
        db=Database(Path(d)/'db.sqlite')
        assert db.one("SELECT value FROM schema_meta WHERE key='schema_version'")['value']=='11'
        try:
            with db.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                c.execute("INSERT INTO audit_log(action) VALUES('rollback_probe')")
                raise RuntimeError('force rollback')
        except RuntimeError:
            pass
        assert db.one("SELECT 1 FROM audit_log WHERE action='rollback_probe'") is None

def test_payment_ticket_type_source_present():
    src=(Path(__file__).parents[1]/'app/views/support_tickets.py').read_text(encoding='utf-8')
    assert "'payment':" in src
