import tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
from app.core.database import Database
from app.services.subscriptions import SubscriptionService
from app.services.indexer import VaultIndexer
from app.services.search import SearchService

class Bot:
 def __init__(self,db):self.db=db

def fresh():
 d=tempfile.TemporaryDirectory();db=Database(Path(d.name)/'x.db');return d,db

def test_tos_validation():
 d,db=fresh()
 for key,bad in [('tos_pass_percent',0),('tos_pass_percent',101),('tos_min_read_seconds',-1),('tos_max_kicks',-1)]:
  try:db.set_guild(1,**{key:bad});assert False,key
  except ValueError:pass
 d.cleanup()

def test_subscription_grace_anchored():
 d,db=fresh();db.seed_plans(1);p=db.one("SELECT * FROM subscription_plans WHERE guild_id=1 AND lifetime=0 LIMIT 1");svc=SubscriptionService(Bot(db));end=datetime.now(timezone.utc)+timedelta(days=2);sid,code,_,_=svc.activate(1,2,p['id'],'test','sub-1',auto_renew=True,billing_period_end=end.isoformat());g1=svc.mark_past_due(sid);g2=svc.mark_past_due(sid);assert g1==g2==end+timedelta(days=p['grace_days']);r=db.one('SELECT * FROM subscriptions WHERE id=?',(sid,));assert r['billing_period_end']==end.isoformat();d.cleanup()

def test_fulfill_idempotent():
 d,db=fresh();db.seed_plans(1);p=db.one("SELECT * FROM subscription_plans WHERE guild_id=1 AND lifetime=0 LIMIT 1");svc=SubscriptionService(Bot(db));sid=svc.create_pending(1,2,p['id'],'test','sub-x');a=svc.fulfill_pending(sid);b=svc.fulfill_pending(sid);assert a[0]==b[0] and b[3] is False;assert db.one('SELECT COUNT(*) n FROM entitlements WHERE subscription_id=?',(sid,))['n']==1;d.cleanup()

def test_vault_fts_incremental_and_cross_guild():
 d,db=fresh();root=Path(d.name)/'vault';root.mkdir();(root/'Kick One.wav').write_bytes(b'x');VaultIndexer(db).scan(1,str(root));assert SearchService(db).search('Kick',guild_id=1).total==1;assert SearchService(db).search('Kick',guild_id=2).total==0;(root/'Snare.wav').write_bytes(b'y');VaultIndexer(db).scan(1,str(root));assert SearchService(db).search('Snare',guild_id=1).total==1;d.cleanup()

if __name__=='__main__':
 for f in [test_tos_validation,test_subscription_grace_anchored,test_fulfill_idempotent,test_vault_fts_incremental_and_cross_guild]:f()
 print('v3.9 tests passed')

def test_manual_approval_idempotent():
 d,db=fresh();db.seed_plans(1);p=db.one("SELECT * FROM subscription_plans WHERE guild_id=1 AND lifetime=0 LIMIT 1");tx=db.execute("INSERT INTO transactions(guild_id,user_id,plan_id,provider,status) VALUES(1,2,?,'cashapp','pending_manual')",(p['id'],));svc=SubscriptionService(Bot(db));a=svc.approve_manual_transaction(tx);b=svc.approve_manual_transaction(tx);assert a[1]==b[1] and b[4] is False;assert db.one('SELECT COUNT(*) n FROM subscriptions WHERE guild_id=1 AND user_id=2')['n']==1;d.cleanup()
