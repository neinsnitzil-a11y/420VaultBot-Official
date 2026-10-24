import tempfile, threading
from pathlib import Path
from app.core.database import Database
from app.services.webhooks import WebhookServer

class Bot:
    def __init__(self,db): self.db=db

def test_webhook_claim_is_atomic():
    with tempfile.TemporaryDirectory() as d:
        db=Database(Path(d)/'x.db'); w=WebhookServer(Bot(db)); out=[]
        def claim(): out.append(w._reserve('stripe','evt_same',b'{}'))
        ts=[threading.Thread(target=claim) for _ in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]
        assert sum(bool(x) for x in out)==1, out
        row=db.one("SELECT state,attempt_count FROM webhook_events WHERE provider='stripe' AND event_id='evt_same'")
        assert row['state']=='processing' and row['attempt_count']==1

def test_async_db_helpers_exist():
    assert all(hasattr(Database,n) for n in ('aone','aall','aexecute'))

def test_schema_v13():
    with tempfile.TemporaryDirectory() as d:
        db=Database(Path(d)/'x.db'); r=db.one("SELECT value FROM schema_meta WHERE key='schema_version'")
        assert r['value']=='13'
