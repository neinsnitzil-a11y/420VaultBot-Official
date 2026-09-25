from __future__ import annotations
import sqlite3
import asyncio
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA='''
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS guild_settings (guild_id INTEGER PRIMARY KEY,search_channel_id INTEGER,license_channel_id INTEGER,log_channel_id INTEGER,admin_role_id INTEGER,member_role_id INTEGER,verified_role_id INTEGER,unverified_role_id INTEGER,subscribed_role_id INTEGER,beta_role_id INTEGER,overseer_role_id INTEGER,tos_channel_id INTEGER,tos_message_id INTEGER,ticket_channel_id INTEGER,ticket_message_id INTEGER,tos_enabled INTEGER NOT NULL DEFAULT 1,tos_min_read_seconds INTEGER NOT NULL DEFAULT 60,tos_pass_percent INTEGER NOT NULL DEFAULT 80,tos_max_kicks INTEGER NOT NULL DEFAULT 3,vault_path TEXT,results_per_page INTEGER NOT NULL DEFAULT 5,max_search_results INTEGER NOT NULL DEFAULT 250,licensing_enabled INTEGER NOT NULL DEFAULT 1,downloads_enabled INTEGER NOT NULL DEFAULT 1,setup_completed INTEGER NOT NULL DEFAULT 0,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS vault_files (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL DEFAULT 0,filename TEXT NOT NULL,full_path TEXT NOT NULL,folder TEXT NOT NULL DEFAULT '',extension TEXT NOT NULL DEFAULT '',category TEXT NOT NULL DEFAULT 'other',file_size INTEGER NOT NULL DEFAULT 0,modified_at REAL NOT NULL DEFAULT 0,checksum TEXT,available INTEGER NOT NULL DEFAULT 1,UNIQUE(guild_id,full_path));
CREATE INDEX IF NOT EXISTS idx_vault_filename ON vault_files(guild_id,filename COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_vault_folder ON vault_files(guild_id,folder COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS vault_folders (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,name TEXT NOT NULL,relative_path TEXT NOT NULL,full_path TEXT NOT NULL,modified_at REAL NOT NULL DEFAULT 0,child_count INTEGER NOT NULL DEFAULT 0,available INTEGER NOT NULL DEFAULT 1,UNIQUE(guild_id,relative_path));
CREATE INDEX IF NOT EXISTS idx_vault_folders_name ON vault_folders(guild_id,name COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS vault_scan_state (guild_id INTEGER PRIMARY KEY,last_scan TEXT,last_status TEXT,last_error TEXT);
CREATE VIRTUAL TABLE IF NOT EXISTS vault_fts USING fts5(kind UNINDEXED,item_id UNINDEXED,guild_id UNINDEXED,name,path,extension,category);
CREATE TABLE IF NOT EXISTS licenses (code TEXT PRIMARY KEY,guild_id INTEGER NOT NULL,user_id INTEGER,status TEXT NOT NULL DEFAULT 'active',expires_at TEXT,max_activations INTEGER NOT NULL DEFAULT 1,activations INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,assigned_user_id INTEGER,signature_hmac TEXT,entitlement_id INTEGER);
CREATE TABLE IF NOT EXISTS entitlements (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,source TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'active',starts_at TEXT NOT NULL,expires_at TEXT,grace_until TEXT,subscription_id INTEGER,granted_by INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_entitlement_user ON entitlements(guild_id,user_id,status);
CREATE TABLE IF NOT EXISTS payment_tickets (transaction_id INTEGER PRIMARY KEY,guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,channel_id INTEGER,status TEXT NOT NULL DEFAULT 'open',ticket_type TEXT NOT NULL DEFAULT 'manual_approval',provider TEXT,provider_event_id TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS support_tickets (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,channel_id INTEGER NOT NULL UNIQUE,ticket_type TEXT NOT NULL,subject TEXT DEFAULT '',status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,closed_at TEXT);
CREATE INDEX IF NOT EXISTS idx_support_tickets_user ON support_tickets(guild_id,user_id,status);
CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER,user_id INTEGER,action TEXT NOT NULL,details TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS guild_channels (guild_id INTEGER NOT NULL,channel_id INTEGER NOT NULL,purpose TEXT NOT NULL,PRIMARY KEY(guild_id,channel_id,purpose));
CREATE TABLE IF NOT EXISTS subscription_plans (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,name TEXT NOT NULL,description TEXT DEFAULT '',price_cents INTEGER NOT NULL,currency TEXT NOT NULL DEFAULT 'USD',duration_days INTEGER,lifetime INTEGER NOT NULL DEFAULT 0,enabled INTEGER NOT NULL DEFAULT 1,role_id INTEGER,features TEXT DEFAULT '',auto_renew INTEGER NOT NULL DEFAULT 1,grace_days INTEGER NOT NULL DEFAULT 7,provider_availability TEXT DEFAULT 'cashapp,stripe,paypal',stripe_price_id TEXT,paypal_plan_id TEXT,UNIQUE(guild_id,name));
CREATE TABLE IF NOT EXISTS subscriptions (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,plan_id INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',started_at TEXT,billing_period_end TEXT,expires_at TEXT,grace_until TEXT,auto_renew INTEGER NOT NULL DEFAULT 0,provider TEXT,provider_customer_id TEXT,provider_subscription_id TEXT,license_code TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_sub_user ON subscriptions(guild_id,user_id,status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_subscription ON subscriptions(provider,provider_subscription_id) WHERE provider_subscription_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,plan_id INTEGER,subscription_id INTEGER,provider TEXT NOT NULL,provider_transaction_id TEXT,provider_event_id TEXT,amount_cents INTEGER,currency TEXT,status TEXT NOT NULL DEFAULT 'pending',proof_url TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(provider,provider_transaction_id),UNIQUE(provider,provider_event_id));
CREATE TABLE IF NOT EXISTS payment_settings (guild_id INTEGER NOT NULL,provider TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,config_json TEXT NOT NULL DEFAULT '{}',PRIMARY KEY(guild_id,provider));
CREATE TABLE IF NOT EXISTS webhook_events (provider TEXT NOT NULL,event_id TEXT NOT NULL,received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,processed_at TEXT,payload_hash TEXT,state TEXT NOT NULL DEFAULT 'received',attempt_count INTEGER NOT NULL DEFAULT 0,last_error TEXT,last_attempt_at TEXT,PRIMARY KEY(provider,event_id));
CREATE TABLE IF NOT EXISTS link_lists (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,name TEXT NOT NULL,description TEXT DEFAULT '',source_type TEXT NOT NULL DEFAULT 'import',source_url TEXT,enabled INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(guild_id,name));
CREATE TABLE IF NOT EXISTS links (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,url TEXT NOT NULL,normalized_url TEXT NOT NULL,domain TEXT NOT NULL DEFAULT '',title TEXT DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(guild_id,normalized_url));
CREATE TABLE IF NOT EXISTS link_list_members (list_id INTEGER NOT NULL,link_id INTEGER NOT NULL,PRIMARY KEY(list_id,link_id));
CREATE INDEX IF NOT EXISTS idx_links_domain ON links(guild_id,domain);
CREATE VIRTUAL TABLE IF NOT EXISTS link_fts USING fts5(link_id UNINDEXED,guild_id UNINDEXED,url,domain,title);
CREATE TABLE IF NOT EXISTS scrape_jobs (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,target_url TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'queued',pages_crawled INTEGER NOT NULL DEFAULT 0,links_found INTEGER NOT NULL DEFAULT 0,errors INTEGER NOT NULL DEFAULT 0,output_path TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,finished_at TEXT,last_error TEXT);
CREATE TABLE IF NOT EXISTS tos_acceptance (guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,tos_version TEXT NOT NULL,accepted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,quiz_score INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(guild_id,user_id));
CREATE TABLE IF NOT EXISTS tos_attempts (guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,failed_sessions INTEGER NOT NULL DEFAULT 0,last_attempt_at TEXT,last_result TEXT,PRIMARY KEY(guild_id,user_id));
CREATE TABLE IF NOT EXISTS remote_sources (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,name TEXT NOT NULL,manifest_url TEXT NOT NULL,auth_token TEXT,enabled INTEGER NOT NULL DEFAULT 1,last_sync TEXT,last_status TEXT NOT NULL DEFAULT 'new',UNIQUE(guild_id,name));
CREATE TABLE IF NOT EXISTS remote_items (id INTEGER PRIMARY KEY AUTOINCREMENT,source_id INTEGER NOT NULL,guild_id INTEGER NOT NULL,name TEXT NOT NULL,path TEXT NOT NULL,size INTEGER NOT NULL DEFAULT 0,download_url TEXT NOT NULL,preview_url TEXT,available INTEGER NOT NULL DEFAULT 1,UNIQUE(source_id,path));
CREATE INDEX IF NOT EXISTS idx_remote_items_search ON remote_items(guild_id,name,path);
CREATE TABLE IF NOT EXISTS license_orders (order_id TEXT PRIMARY KEY,guild_id INTEGER NOT NULL,user_id INTEGER NOT NULL,license_code TEXT,status TEXT NOT NULL DEFAULT 'issued',note TEXT,created_by INTEGER,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_license_orders_user ON license_orders(guild_id,user_id,created_at);
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS drive_sources (guild_id INTEGER PRIMARY KEY,root_file_id TEXT NOT NULL,root_name TEXT NOT NULL DEFAULT 'Google Drive',enabled INTEGER NOT NULL DEFAULT 1,last_sync TEXT,last_status TEXT,item_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS drive_items (guild_id INTEGER NOT NULL,file_id TEXT NOT NULL,parent_id TEXT,name TEXT NOT NULL,mime_type TEXT NOT NULL,size INTEGER NOT NULL DEFAULT 0,modified_time TEXT,web_view_link TEXT,relative_path TEXT NOT NULL DEFAULT '',is_folder INTEGER NOT NULL DEFAULT 0,available INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(guild_id,file_id));
CREATE INDEX IF NOT EXISTS idx_drive_parent ON drive_items(guild_id,parent_id,is_folder,name);
CREATE VIRTUAL TABLE IF NOT EXISTS drive_fts USING fts5(file_id UNINDEXED,guild_id UNINDEXED,name,path,mime_type);
CREATE TABLE IF NOT EXISTS drive_archive_entries (id INTEGER PRIMARY KEY AUTOINCREMENT,guild_id INTEGER NOT NULL,archive_file_id TEXT NOT NULL,archive_name TEXT NOT NULL,member_name TEXT NOT NULL,member_path TEXT NOT NULL,member_size INTEGER NOT NULL DEFAULT 0,archive_modified_time TEXT,UNIQUE(guild_id,archive_file_id,member_path));
CREATE INDEX IF NOT EXISTS idx_drive_archive_parent ON drive_archive_entries(guild_id,archive_file_id);
CREATE VIRTUAL TABLE IF NOT EXISTS drive_archive_fts USING fts5(entry_id UNINDEXED,guild_id UNINDEXED,archive_name,member_name,member_path);
CREATE TABLE IF NOT EXISTS drive_archive_state (guild_id INTEGER PRIMARY KEY,last_run TEXT,last_status TEXT,archives_parsed INTEGER NOT NULL DEFAULT 0,entries_indexed INTEGER NOT NULL DEFAULT 0,last_error TEXT);
INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version','17');
'''
class Database:
 def __init__(self,path:Path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as c:
   cols=[r[1] for r in c.execute('PRAGMA table_info(vault_files)').fetchall()]
   if cols and ('guild_id' not in cols or 'category' not in cols or 'available' not in cols):c.execute('ALTER TABLE vault_files RENAME TO vault_files_legacy_v31')
   c.executescript(SCHEMA)
   gcols=[r[1] for r in c.execute('PRAGMA table_info(guild_settings)').fetchall()]
   additions={'verified_role_id':'INTEGER','unverified_role_id':'INTEGER','subscribed_role_id':'INTEGER','beta_role_id':'INTEGER','overseer_role_id':'INTEGER','tos_channel_id':'INTEGER','tos_message_id':'INTEGER','ticket_channel_id':'INTEGER','ticket_message_id':'INTEGER','tos_enabled':'INTEGER NOT NULL DEFAULT 1','tos_min_read_seconds':'INTEGER NOT NULL DEFAULT 60','tos_pass_percent':'INTEGER NOT NULL DEFAULT 80','tos_max_kicks':'INTEGER NOT NULL DEFAULT 3'}
   for col,typ in additions.items():
    if col not in gcols:c.execute(f'ALTER TABLE guild_settings ADD COLUMN {col} {typ}')
   lcols=[r[1] for r in c.execute('PRAGMA table_info(licenses)').fetchall()]
   if 'signature_hmac' not in lcols:c.execute('ALTER TABLE licenses ADD COLUMN signature_hmac TEXT')
   if 'entitlement_id' not in lcols:c.execute('ALTER TABLE licenses ADD COLUMN entitlement_id INTEGER')
   ptcols=[r[1] for r in c.execute('PRAGMA table_info(payment_tickets)').fetchall()]
   if 'ticket_type' not in ptcols:c.execute("ALTER TABLE payment_tickets ADD COLUMN ticket_type TEXT NOT NULL DEFAULT 'manual_approval'")
   if 'provider' not in ptcols:c.execute('ALTER TABLE payment_tickets ADD COLUMN provider TEXT')
   if 'provider_event_id' not in ptcols:c.execute('ALTER TABLE payment_tickets ADD COLUMN provider_event_id TEXT')
   whcols=[r[1] for r in c.execute('PRAGMA table_info(webhook_events)').fetchall()]
   if 'state' not in whcols:c.execute("ALTER TABLE webhook_events ADD COLUMN state TEXT NOT NULL DEFAULT 'received'")
   if 'attempt_count' not in whcols:c.execute("ALTER TABLE webhook_events ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0")
   if 'last_error' not in whcols:c.execute('ALTER TABLE webhook_events ADD COLUMN last_error TEXT')
   if 'last_attempt_at' not in whcols:c.execute('ALTER TABLE webhook_events ADD COLUMN last_attempt_at TEXT')
   if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vault_files_legacy_v31'").fetchone():
    c.execute("INSERT OR IGNORE INTO vault_files(guild_id,filename,full_path,folder,extension,file_size,modified_at,checksum) SELECT 0,filename,full_path,folder,extension,file_size,modified_at,checksum FROM vault_files_legacy_v31")
   scols=[r[1] for r in c.execute('PRAGMA table_info(subscriptions)').fetchall()]
   if 'billing_period_end' not in scols:c.execute('ALTER TABLE subscriptions ADD COLUMN billing_period_end TEXT')
   # Preserve legacy backup tables; never drop them automatically.
   c.execute("INSERT OR REPLACE INTO schema_meta(key,value) VALUES('schema_version','17')")
 def connect(self):
  class Ctx:
   def __init__(x,db):
    # IMPORTANT: never acquire a process-wide threading lock here. connect() is
    # also used by Discord callbacks; a blocking lock on the event-loop thread
    # prevents gateway heartbeats and makes every component look dead. WAL +
    # SQLite's busy handler coordinate short transactions across connections.
    x.c=sqlite3.connect(db.path,timeout=5.0);x.c.row_factory=sqlite3.Row
    x.c.execute('PRAGMA busy_timeout=5000')
    x.c.execute('PRAGMA synchronous=NORMAL')
    x.c.execute('PRAGMA foreign_keys=ON')
   def __enter__(x):return x.c
   def __exit__(x,exc_type,exc,tb):
    try:x.c.commit() if exc_type is None else x.c.rollback()
    finally:x.c.close()
    return False
  return Ctx(self)
 def _retry(self,fn):
  delay=0.03
  for attempt in range(7):
   try:return fn()
   except sqlite3.OperationalError as e:
    if 'locked' not in str(e).lower() and 'busy' not in str(e).lower():raise
    if attempt==6:raise
    time.sleep(delay);delay=min(delay*2,0.5)
 def one(self,sql,params=()):
  def op():
   with self.connect() as c:return c.execute(sql,params).fetchone()
  return self._retry(op)
 def all(self,sql,params=()):
  def op():
   with self.connect() as c:return c.execute(sql,params).fetchall()
  return self._retry(op)
 def execute(self,sql,params=()):
  def op():
   with self.connect() as c:return c.execute(sql,params).lastrowid
  return self._retry(op)
 def aone(self,sql,params=()): return asyncio.to_thread(self.one,sql,params)
 def aall(self,sql,params=()): return asyncio.to_thread(self.all,sql,params)
 def aexecute(self,sql,params=()): return asyncio.to_thread(self.execute,sql,params)
 def guild(self,guild_id:int)->dict[str,Any]:
  # Read first. INSERT OR IGNORE on every read unnecessarily requested a writer lock.
  row=self.one('SELECT * FROM guild_settings WHERE guild_id=?',(guild_id,))
  if row is None:
   self.execute('INSERT OR IGNORE INTO guild_settings(guild_id) VALUES(?)',(guild_id,));row=self.one('SELECT * FROM guild_settings WHERE guild_id=?',(guild_id,))
  return dict(row)
 def set_guild(self,guild_id:int,**values):
  if 'tos_pass_percent' in values and not 1<=int(values['tos_pass_percent'])<=100:raise ValueError('tos_pass_percent must be 1-100')
  if 'tos_min_read_seconds' in values and not 0<=int(values['tos_min_read_seconds'])<=86400:raise ValueError('tos_min_read_seconds must be 0-86400')
  if 'tos_max_kicks' in values and not 0<=int(values['tos_max_kicks'])<=100:raise ValueError('tos_max_kicks must be 0-100')
  allowed={'search_channel_id','license_channel_id','log_channel_id','admin_role_id','member_role_id','verified_role_id','unverified_role_id','subscribed_role_id','beta_role_id','overseer_role_id','tos_channel_id','tos_message_id','ticket_channel_id','ticket_message_id','tos_enabled','tos_min_read_seconds','tos_pass_percent','tos_max_kicks','vault_path','results_per_page','max_search_results','licensing_enabled','downloads_enabled','setup_completed'};values={k:v for k,v in values.items() if k in allowed}
  if not values:return
  self.execute('INSERT OR IGNORE INTO guild_settings(guild_id) VALUES(?)',(guild_id,));cols=', '.join(f'{k}=?' for k in values);self.execute(f'UPDATE guild_settings SET {cols},updated_at=CURRENT_TIMESTAMP WHERE guild_id=?',(*values.values(),guild_id))
 def channels(self,guild_id,purpose):return [int(r['channel_id']) for r in self.all('SELECT channel_id FROM guild_channels WHERE guild_id=? AND purpose=? ORDER BY channel_id',(guild_id,purpose))]
 def set_channels(self,guild_id,purpose,ids):
  self.execute('DELETE FROM guild_channels WHERE guild_id=? AND purpose=?',(guild_id,purpose))
  for cid in dict.fromkeys(int(x) for x in ids):self.execute('INSERT OR IGNORE INTO guild_channels VALUES(?,?,?)',(guild_id,cid,purpose))
 def seed_plans(self,gid:int):
  # Premium default catalog. INSERT OR IGNORE keeps every plan editable in the Admin GUI.
  # The small migration below only changes untouched legacy defaults; customized admin plans are preserved.
  legacy=[
   ('Half Year',5000,182,0,'6 Months','Six months of 420Vault access',10000,182,0),
   ('Yearly',10000,365,0,'1 Year','One year of 420Vault access',15000,365,0),
   ('Lifetime',15000,None,1,'Lifetime','Indefinite access; no automatic expiry',50000,None,1),
  ]
  for old_name,old_price,old_days,old_life,new_name,desc,new_price,new_days,new_life in legacy:
   row=self.one('SELECT id,name,price_cents,duration_days,lifetime FROM subscription_plans WHERE guild_id=? AND name=?',(gid,old_name))
   if row and int(row['price_cents'])==old_price and row['duration_days']==old_days and int(row['lifetime'])==old_life:
    # Do not overwrite a separately-created plan that already uses the new name.
    clash=self.one('SELECT id FROM subscription_plans WHERE guild_id=? AND name=? AND id<>?',(gid,new_name,row['id']))
    if not clash:self.execute('UPDATE subscription_plans SET name=?,description=?,price_cents=?,duration_days=?,lifetime=?,auto_renew=? WHERE id=?',(new_name,desc,new_price,new_days,new_life,0 if new_life else 1,row['id']))
  defaults=[
   ('1 Month','One month of 420Vault access',2500,30,0),
   ('3 Months','Three months of 420Vault access',7500,90,0),
   ('6 Months','Six months of 420Vault access',10000,182,0),
   ('1 Year','One year of 420Vault access',15000,365,0),
   ('2 Years','Two years of 420Vault access',20000,730,0),
   ('3 Years','Three years of 420Vault access',25000,1095,0),
   ('Lifetime','Indefinite access; no automatic expiry',50000,None,1),
  ]
  for n,d,p,days,life in defaults:self.execute('INSERT OR IGNORE INTO subscription_plans(guild_id,name,description,price_cents,duration_days,lifetime,auto_renew) VALUES(?,?,?,?,?,?,?)',(gid,n,d,p,days,life,0 if life else 1))
 def rebuild_vault_fts(self,gid:int):
  with self.connect() as c:
   c.execute('DELETE FROM vault_fts WHERE guild_id=?',(gid,));c.execute("INSERT INTO vault_fts(kind,item_id,guild_id,name,path,extension,category) SELECT 'file',id,guild_id,filename,folder,extension,category FROM vault_files WHERE guild_id=?",(gid,));c.execute("INSERT INTO vault_fts(kind,item_id,guild_id,name,path,extension,category) SELECT 'folder',id,guild_id,name,relative_path,'','folder' FROM vault_folders WHERE guild_id=?",(gid,))
 def vault_stats(self,gid:int):
  f=self.one('SELECT COUNT(*) n,COALESCE(SUM(file_size),0) size FROM vault_files WHERE guild_id=?',(gid,));d=self.one('SELECT COUNT(*) n FROM vault_folders WHERE guild_id=?',(gid,));st=self.one('SELECT * FROM vault_scan_state WHERE guild_id=?',(gid,));return {'files':f['n'],'size':f['size'],'folders':d['n'],'last_scan':st['last_scan'] if st else None,'status':st['last_status'] if st else None}
 def audit(self,gid,uid,action,details=''):self.execute('INSERT INTO audit_log(guild_id,user_id,action,details) VALUES(?,?,?,?)',(gid,uid,action,details[:1000]))
