from __future__ import annotations
from datetime import datetime,timedelta,timezone
from app.core.licensing import make_license_code,license_signature

def now():return datetime.now(timezone.utc)
def dt(v):
 if not v:return None
 if isinstance(v,datetime):return v
 return datetime.fromisoformat(str(v).replace('Z','+00:00'))

class SubscriptionService:
 def __init__(self,bot):self.bot=bot;self.db=bot.db
 def entitlement_for(self,gid,uid):
  t=now().isoformat();return self.db.one("SELECT * FROM entitlements WHERE guild_id=? AND user_id=? AND status='active' AND ((expires_at IS NULL OR expires_at>?) OR (grace_until IS NOT NULL AND grace_until>?)) ORDER BY id DESC LIMIT 1",(gid,uid,t,t))
 def active_for(self,gid,uid):
  t=now().isoformat();return self.db.one("SELECT s.*,p.name plan_name,p.lifetime FROM subscriptions s JOIN subscription_plans p ON p.id=s.plan_id WHERE s.guild_id=? AND s.user_id=? AND (s.status='active' OR (s.status='past_due' AND s.grace_until>?)) ORDER BY s.id DESC LIMIT 1",(gid,uid,t))
 def _license_tx(self,c,gid,uid,exp,eid):
  code=make_license_code();sig=license_signature(code);c.execute('INSERT INTO licenses(code,guild_id,user_id,status,expires_at,max_activations,activations,assigned_user_id,signature_hmac,entitlement_id) VALUES(?,?,NULL,?,?,?,?,?,?,?)',(code,gid,'active',exp.isoformat() if exp else None,1,0,uid,sig,eid));return code
 def admin_grant(self,gid,uid,days,admin_id):
  start=now();exp=None if not days else start+timedelta(days=int(days))
  with self.db.connect() as c:
   c.execute('BEGIN IMMEDIATE');cur=c.execute("INSERT INTO entitlements(guild_id,user_id,source,status,starts_at,expires_at,granted_by) VALUES(?,?,?,'active',?,?,?)",(gid,uid,'admin_grant',start.isoformat(),exp.isoformat() if exp else None,admin_id));eid=cur.lastrowid;code=self._license_tx(c,gid,uid,exp,eid)
  return eid,code,exp
 def _activate_tx(self,c,gid,uid,plan_id,provider,provider_sub=None,provider_customer=None,auto_renew=False,billing_period_end=None):
  start=now();p=c.execute('SELECT * FROM subscription_plans WHERE id=? AND guild_id=?',(plan_id,gid)).fetchone()
  if not p:raise ValueError('Plan not found')
  if provider_sub:
   old=c.execute('SELECT * FROM subscriptions WHERE provider=? AND provider_subscription_id=?',(provider,provider_sub)).fetchone()
   if old and old['license_code']:
    return old['id'],old['license_code'],dict(p),dt(old['billing_period_end'] or old['expires_at'])
  exp=None if p['lifetime'] else (dt(billing_period_end) or start+timedelta(days=int(p['duration_days'])))
  cur=c.execute("INSERT INTO subscriptions(guild_id,user_id,plan_id,status,started_at,billing_period_end,expires_at,auto_renew,provider,provider_customer_id,provider_subscription_id) VALUES(?,?,?,'active',?,?,?,?,?,?,?)",(gid,uid,plan_id,start.isoformat(),exp.isoformat() if exp else None,exp.isoformat() if exp else None,1 if auto_renew else 0,provider,provider_customer,provider_sub));sid=cur.lastrowid
  cur=c.execute("INSERT INTO entitlements(guild_id,user_id,source,status,starts_at,expires_at,subscription_id) VALUES(?,?,?,'active',?,?,?)",(gid,uid,'subscription',start.isoformat(),exp.isoformat() if exp else None,sid));eid=cur.lastrowid;code=self._license_tx(c,gid,uid,exp,eid);c.execute('UPDATE subscriptions SET license_code=? WHERE id=?',(code,sid));return sid,code,dict(p),exp
 def activate(self,gid,uid,plan_id,provider,provider_sub=None,provider_customer=None,auto_renew=False,billing_period_end=None):
  with self.db.connect() as c:
   c.execute('BEGIN IMMEDIATE');return self._activate_tx(c,gid,uid,plan_id,provider,provider_sub,provider_customer,auto_renew,billing_period_end)
 def approve_manual_transaction(self,txid):
  with self.db.connect() as c:
   c.execute('BEGIN IMMEDIATE');t=c.execute("SELECT * FROM transactions WHERE id=?",(txid,)).fetchone()
   if not t:raise ValueError('Transaction not found')
   if t['status']=='paid':
    sub=c.execute('SELECT * FROM subscriptions WHERE id=?',(t['subscription_id'],)).fetchone();p=c.execute('SELECT * FROM subscription_plans WHERE id=?',(t['plan_id'],)).fetchone();return t['subscription_id'],sub['license_code'],dict(p),dt(sub['billing_period_end'] or sub['expires_at']),False
   if t['status']!='pending_manual':raise ValueError('Payment already handled or processing')
   sid,code,p,exp=self._activate_tx(c,t['guild_id'],t['user_id'],t['plan_id'],'cashapp',f'manual:{txid}',None,False,None)
   cur=c.execute("UPDATE transactions SET status='paid',subscription_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending_manual'",(sid,txid))
   if cur.rowcount!=1:raise RuntimeError('Atomic payment claim failed')
   c.execute("UPDATE payment_tickets SET status='approved' WHERE transaction_id=?",(txid,));return sid,code,p,exp,True
 def create_pending(self,gid,uid,plan_id,provider,provider_sub,provider_customer=None,auto_renew=True):
  with self.db.connect() as c:
   c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT id FROM subscriptions WHERE provider=? AND provider_subscription_id=?',(provider,provider_sub)).fetchone()
   if old:return int(old['id'])
   return c.execute("INSERT INTO subscriptions(guild_id,user_id,plan_id,status,auto_renew,provider,provider_customer_id,provider_subscription_id) VALUES(?,?,?,'pending',?,?,?,?)",(gid,uid,plan_id,1 if auto_renew else 0,provider,provider_customer,provider_sub)).lastrowid
 def fulfill_pending(self,sid,expires_at=None):
  with self.db.connect() as c:
   c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM subscriptions WHERE id=?',(sid,)).fetchone()
   if not r:raise ValueError('Subscription not found')
   p=c.execute('SELECT * FROM subscription_plans WHERE id=?',(r['plan_id'],)).fetchone()
   if r['license_code']:return r['license_code'],dict(p),r['billing_period_end'] or r['expires_at'],False
   start=now();exp=None if p['lifetime'] else (dt(expires_at) or start+timedelta(days=int(p['duration_days'])))
   cur=c.execute("INSERT INTO entitlements(guild_id,user_id,source,status,starts_at,expires_at,subscription_id) VALUES(?,?,?,'active',?,?,?)",(r['guild_id'],r['user_id'],'subscription',start.isoformat(),exp.isoformat() if exp else None,sid));eid=cur.lastrowid;code=self._license_tx(c,r['guild_id'],r['user_id'],exp,eid);c.execute("UPDATE subscriptions SET status='active',started_at=?,billing_period_end=?,expires_at=?,grace_until=NULL,license_code=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND license_code IS NULL",(start.isoformat(),exp.isoformat() if exp else None,exp.isoformat() if exp else None,code,sid))
  return code,dict(p),exp,True
 def renew(self,sid,billing_period_end):
  exp=dt(billing_period_end)
  if not exp:raise ValueError('Provider billing period end required')
  with self.db.connect() as c:
   c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM subscriptions WHERE id=?',(sid,)).fetchone()
   if not r:raise ValueError('Subscription not found')
   c.execute("UPDATE subscriptions SET status='active',billing_period_end=?,expires_at=?,grace_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?",(exp.isoformat(),exp.isoformat(),sid));c.execute("UPDATE entitlements SET status='active',expires_at=?,grace_until=NULL WHERE subscription_id=?",(exp.isoformat(),sid));c.execute("UPDATE licenses SET status='active',expires_at=? WHERE code=?",(exp.isoformat(),r['license_code']))
  return exp
 def mark_past_due(self,sid,grace_days=None):
  with self.db.connect() as c:
   c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT s.*,p.grace_days FROM subscriptions s JOIN subscription_plans p ON p.id=s.plan_id WHERE s.id=?',(sid,)).fetchone()
   if not r:raise ValueError('Subscription not found')
   base=dt(r['billing_period_end'] or r['expires_at']) or now();days=int(r['grace_days'] if grace_days is None else grace_days);grace=base+timedelta(days=days)
   # one grace window per billing period; never base it on a previous grace_until
   c.execute("UPDATE subscriptions SET status='past_due',grace_until=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(grace.isoformat(),sid));c.execute("UPDATE entitlements SET status='active',expires_at=?,grace_until=? WHERE subscription_id=?",(base.isoformat(),grace.isoformat(),sid))
  return grace
 def expire_due(self):
  t=now();rows=self.db.all("SELECT s.*,p.lifetime FROM subscriptions s JOIN subscription_plans p ON p.id=s.plan_id WHERE s.status IN ('active','past_due') AND p.lifetime=0",());changed=[]
  for s in rows:
   end=dt(s['billing_period_end'] or s['expires_at']);grace=dt(s['grace_until'])
   if s['status']=='active' and end and t>=end:
    if s['auto_renew']:self.mark_past_due(s['id']);continue
   deadline=grace if s['status']=='past_due' and grace else end
   if deadline and t>=deadline:
    with self.db.connect() as c:
     c.execute('BEGIN IMMEDIATE');c.execute("UPDATE subscriptions SET status='expired',updated_at=CURRENT_TIMESTAMP WHERE id=?",(s['id'],));c.execute("UPDATE entitlements SET status='expired' WHERE subscription_id=?",(s['id'],));c.execute("UPDATE licenses SET status='expired' WHERE code=?",(s['license_code'],))
    changed.append(dict(s))
  self.db.execute("UPDATE entitlements SET status='expired' WHERE source='admin_grant' AND status='active' AND expires_at IS NOT NULL AND expires_at<=?",(t.isoformat(),));self.db.execute("UPDATE licenses SET status='expired' WHERE entitlement_id IN (SELECT id FROM entitlements WHERE status='expired') AND status='active'")
  return changed
