from __future__ import annotations
import hmac, os
from aiohttp import web
from app.views.support_tickets import TYPES, create_support_ticket
from app.services.access import check_access


def _row(r): return dict(r) if r is not None else None
def _rows(rs): return [dict(r) for r in rs]

def _safe_license(r):
    d=_row(r)
    if not d:return None
    d.pop('signature_hmac',None)
    return d

class WebAPI:
    """Authenticated Base44/server-to-server API over the same aiohttp listener as webhooks."""
    def __init__(self,bot): self.bot=bot

    def register(self,app:web.Application):
        app.router.add_get('/api/v1/status',self.status)
        app.router.add_get('/api/v1/plans',self.plans)
        app.router.add_get('/api/v1/me',self.me)
        app.router.add_get('/api/v1/licenses/me',self.my_licenses)
        app.router.add_post('/api/v1/licenses/resend',self.resend_license)
        app.router.add_get('/api/v1/subscriptions/me',self.my_subscriptions)
        app.router.add_get('/api/v1/payments/me',self.my_payments)
        app.router.add_get('/api/v1/tickets',self.my_tickets)
        app.router.add_post('/api/v1/tickets',self.create_ticket)
        app.router.add_get('/api/v1/admin/users',self.admin_users)
        app.router.add_get('/api/v1/admin/licenses',self.admin_licenses)
        app.router.add_post('/api/v1/admin/licenses',self.admin_create_license)
        app.router.add_post('/api/v1/admin/licenses/{code}/revoke',self.admin_revoke_license)
        app.router.add_get('/api/v1/admin/subscriptions',self.admin_subscriptions)
        app.router.add_get('/api/v1/admin/transactions',self.admin_transactions)
        app.router.add_get('/api/v1/admin/tickets',self.admin_tickets)
        app.router.add_get('/api/v1/admin/logs',self.admin_logs)
        app.router.add_get('/api/v1/admin/vault',self.admin_vault)

    def _secret_ok(self,req):
        expected=os.getenv('VAULT_API_KEY','').strip()
        auth=req.headers.get('Authorization','')
        supplied=auth[7:].strip() if auth.lower().startswith('bearer ') else req.headers.get('X-420Vault-Key','').strip()
        return len(expected)>=32 and bool(supplied) and hmac.compare_digest(expected,supplied)

    def _identity(self,req,need_user=True):
        if not self._secret_ok(req): raise web.HTTPUnauthorized(text='invalid service credential')
        try: gid=int(req.headers.get('X-Guild-ID') or req.query.get('guild_id',''))
        except Exception: raise web.HTTPBadRequest(text='X-Guild-ID required')
        uid=None
        if need_user:
            try: uid=int(req.headers.get('X-Discord-User-ID') or req.query.get('user_id',''))
            except Exception: raise web.HTTPBadRequest(text='X-Discord-User-ID required')
        return gid,uid

    async def _json(self,req):
        try:return await req.json()
        except Exception:raise web.HTTPBadRequest(text='valid JSON body required')

    def _admin(self,req):
        gid,uid=self._identity(req,True);g=self.bot.get_guild(gid);m=g.get_member(uid) if g else None
        if not m or not check_access(self.bot,g,m,require_admin=True).allowed:raise web.HTTPForbidden(text='Discord administrator or configured 420Vault admin role required')
        return gid,uid

    async def status(self,req):
        if not self._secret_ok(req):raise web.HTTPUnauthorized(text='invalid service credential')
        return web.json_response({'ok':True,'bot_ready':self.bot.is_ready(),'guilds':len(self.bot.guilds),'version':__import__('app.version',fromlist=['VERSION']).VERSION})

    async def plans(self,req):
        gid,_=self._identity(req,False);self.bot.db.seed_plans(gid)
        return web.json_response({'plans':_rows(self.bot.db.all('SELECT * FROM subscription_plans WHERE guild_id=? AND enabled=1 ORDER BY price_cents',(gid,)))})

    async def me(self,req):
        gid,uid=self._identity(req);g=self.bot.get_guild(gid);m=g.get_member(uid) if g else None
        tos=self.bot.db.one('SELECT * FROM tos_acceptance WHERE guild_id=? AND user_id=?',(gid,uid))
        ent=self.bot.subscriptions.entitlement_for(gid,uid);sub=self.bot.subscriptions.active_for(gid,uid)
        lic=self.bot.db.one('SELECT * FROM licenses WHERE guild_id=? AND assigned_user_id=? ORDER BY created_at DESC LIMIT 1',(gid,uid))
        payload={'guild_id':gid,'discord_user_id':uid,'guild_member':bool(m),'tos':_row(tos),'entitlement':_row(ent),'subscription':_row(sub),'license':_safe_license(lic)}
        if m: payload['discord']={'username':str(m),'display_name':m.display_name,'avatar_url':str(m.display_avatar.url),'roles':[r.name for r in m.roles if r.name!='@everyone']}
        return web.json_response(payload)

    async def my_licenses(self,req):
        gid,uid=self._identity(req);return web.json_response({'licenses':[_safe_license(r) for r in self.bot.db.all('SELECT * FROM licenses WHERE guild_id=? AND assigned_user_id=? ORDER BY created_at DESC',(gid,uid))]})

    async def resend_license(self,req):
        gid,uid=self._identity(req);body=await self._json(req);code=str(body.get('code','')).strip().upper()
        r=self.bot.db.one('SELECT * FROM licenses WHERE code=? AND guild_id=? AND assigned_user_id=?',(code,gid,uid))
        if not r:raise web.HTTPNotFound(text='license not found')
        ok=await self.bot.deliver_license(gid,uid,code,None,r['expires_at']);self.bot.db.audit(gid,uid,'api_license_resend',code)
        return web.json_response({'ok':ok,'code':code})

    async def my_subscriptions(self,req):
        gid,uid=self._identity(req);return web.json_response({'subscriptions':_rows(self.bot.db.all('SELECT s.*,p.name plan_name,p.price_cents,p.currency,p.lifetime FROM subscriptions s JOIN subscription_plans p ON p.id=s.plan_id WHERE s.guild_id=? AND s.user_id=? ORDER BY s.id DESC',(gid,uid)))})

    async def my_payments(self,req):
        gid,uid=self._identity(req);return web.json_response({'transactions':_rows(self.bot.db.all('SELECT * FROM transactions WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 100',(gid,uid)))})

    async def my_tickets(self,req):
        gid,uid=self._identity(req);return web.json_response({'tickets':_rows(self.bot.db.all('SELECT * FROM support_tickets WHERE guild_id=? AND user_id=? ORDER BY id DESC',(gid,uid)))})

    async def create_ticket(self,req):
        gid,uid=self._identity(req);body=await self._json(req);kind=str(body.get('type','')).strip().lower();subject=str(body.get('subject','')).strip()[:100];details=str(body.get('details','')).strip()[:1800]
        if kind not in TYPES:raise web.HTTPBadRequest(text='invalid ticket type')
        if not subject or not details:raise web.HTTPBadRequest(text='subject and details required')
        g=self.bot.get_guild(gid);m=g.get_member(uid) if g else None
        if not g or not m:raise web.HTTPConflict(text='user must be a member of the configured Discord server')
        ch=await create_support_ticket(self.bot,g,m,kind,subject,details);r=self.bot.db.one('SELECT * FROM support_tickets WHERE channel_id=?',(ch.id,))
        return web.json_response({'ticket':_row(r)},status=201)

    async def admin_users(self,req):
        gid,_=self._admin(req)
        sql='''SELECT u.user_id, MAX(u.created_at) first_seen, MAX(u.source) access_source,
        (SELECT status FROM subscriptions s WHERE s.guild_id=u.guild_id AND s.user_id=u.user_id ORDER BY id DESC LIMIT 1) subscription_status,
        (SELECT code FROM licenses l WHERE l.guild_id=u.guild_id AND l.assigned_user_id=u.user_id ORDER BY created_at DESC LIMIT 1) license_code
        FROM entitlements u WHERE u.guild_id=? GROUP BY u.user_id ORDER BY u.user_id'''
        return web.json_response({'users':_rows(self.bot.db.all(sql,(gid,)))})

    async def admin_licenses(self,req):
        gid,_=self._admin(req);return web.json_response({'licenses':[_safe_license(r) for r in self.bot.db.all('SELECT * FROM licenses WHERE guild_id=? ORDER BY created_at DESC',(gid,))]})

    async def admin_create_license(self,req):
        gid,actor=self._admin(req);body=await self._json(req)
        try:uid=int(body.get('user_id'));days=body.get('days');days=None if days in (None,'',0,'0') else int(days)
        except Exception:raise web.HTTPBadRequest(text='valid user_id and days required')
        if days is not None and not 1<=days<=3650:raise web.HTTPBadRequest(text='days must be 1-3650 or null for no expiry')
        admin_id=actor;eid,code,exp=self.bot.subscriptions.admin_grant(gid,uid,days,admin_id)
        delivered=await self.bot.deliver_license(gid,uid,code,None,exp);self.bot.db.audit(gid,admin_id or uid,'api_admin_license_create',f'{code} -> {uid}; entitlement={eid}')
        await self.bot.log_event(gid,'LICENSE',f'Website API generated {code} for Discord user {uid}; DM delivered={delivered}.')
        return web.json_response({'license':{'code':code,'guild_id':gid,'assigned_user_id':uid,'entitlement_id':eid,'expires_at':exp.isoformat() if exp else None,'status':'active','activated':False},'dm_delivered':delivered},status=201)

    async def admin_revoke_license(self,req):
        gid,actor=self._admin(req);code=req.match_info['code'].upper();r=self.bot.db.one('SELECT * FROM licenses WHERE code=? AND guild_id=?',(code,gid))
        if not r:raise web.HTTPNotFound(text='license not found')
        with self.bot.db.connect() as c:
            c.execute('BEGIN IMMEDIATE');c.execute("UPDATE licenses SET status='revoked' WHERE code=? AND guild_id=?",(code,gid))
            if r['entitlement_id']:c.execute("UPDATE entitlements SET status='revoked' WHERE id=? AND guild_id=?",(r['entitlement_id'],gid))
        self.bot.db.audit(gid,actor,'api_admin_license_revoke',code);await self.bot.log_event(gid,'LICENSE',f'Website API revoked {code}.',level='WARNING')
        return web.json_response({'ok':True,'code':code,'status':'revoked'})

    async def admin_subscriptions(self,req):
        gid,_=self._admin(req);return web.json_response({'subscriptions':_rows(self.bot.db.all('SELECT s.*,p.name plan_name FROM subscriptions s JOIN subscription_plans p ON p.id=s.plan_id WHERE s.guild_id=? ORDER BY s.id DESC',(gid,)))})
    async def admin_transactions(self,req):
        gid,_=self._admin(req);return web.json_response({'transactions':_rows(self.bot.db.all('SELECT * FROM transactions WHERE guild_id=? ORDER BY id DESC LIMIT 500',(gid,)))})
    async def admin_tickets(self,req):
        gid,_=self._admin(req);return web.json_response({'tickets':_rows(self.bot.db.all('SELECT * FROM support_tickets WHERE guild_id=? ORDER BY id DESC LIMIT 500',(gid,)))})
    async def admin_logs(self,req):
        gid,_=self._admin(req);return web.json_response({'logs':_rows(self.bot.db.all('SELECT * FROM audit_log WHERE guild_id=? ORDER BY id DESC LIMIT 500',(gid,)))})
    async def admin_vault(self,req):
        gid,_=self._admin(req);s=self.bot.db.guild(gid);return web.json_response({'vault_path':s.get('vault_path'),'stats':self.bot.db.vault_stats(gid)})
