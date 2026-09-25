from __future__ import annotations
import os,json,hashlib
from aiohttp import web
from app.services.web_api import WebAPI

class WebhookServer:
 def __init__(self,bot): self.bot=bot; self.runner=None; self.api=WebAPI(bot)
 async def start(self):
  if os.getenv('WEBHOOK_ENABLED','0')!='1' and os.getenv('API_ENABLED','0')!='1': return
  app=web.Application(client_max_size=1024*1024)
  app.router.add_post('/webhooks/stripe',self.stripe); app.router.add_post('/webhooks/paypal',self.paypal); self.api.register(app)
  app.router.add_get('/health',lambda r:web.json_response({'ok':True,'stripe':bool(os.getenv('STRIPE_WEBHOOK_SECRET')),'paypal':bool(os.getenv('PAYPAL_WEBHOOK_ID'))}))
  self.runner=web.AppRunner(app); await self.runner.setup()
  await web.TCPSite(self.runner,os.getenv('WEBHOOK_HOST','127.0.0.1'),int(os.getenv('WEBHOOK_PORT','8420'))).start()
 async def stop(self):
  if self.runner: await self.runner.cleanup()
 def _existing(self,p,e): return self.bot.db.one('SELECT processed_at,state FROM webhook_events WHERE provider=? AND event_id=?',(p,e))
 def _reserve(self,p,e,raw):
  # Atomically claim an event. Concurrent duplicate deliveries cannot both fulfill it.
  with self.bot.db.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   c.execute("INSERT OR IGNORE INTO webhook_events(provider,event_id,payload_hash,state) VALUES(?,?,?,'received')",(p,e,hashlib.sha256(raw).hexdigest()))
   cur=c.execute("""UPDATE webhook_events SET state='processing',attempt_count=attempt_count+1,last_attempt_at=CURRENT_TIMESTAMP,last_error=NULL
      WHERE provider=? AND event_id=? AND processed_at IS NULL
      AND (state IN ('received','failed') OR (state='processing' AND last_attempt_at < datetime('now','-5 minutes')))""",(p,e))
   return cur.rowcount==1
 def _done(self,p,e): self.bot.db.execute("UPDATE webhook_events SET state='processed',processed_at=CURRENT_TIMESTAMP,last_error=NULL WHERE provider=? AND event_id=?",(p,e))
 async def _process(self,p,ev,raw):
  eid=ev.get('id')
  old=self._existing(p,eid)
  if old and old['processed_at']: return web.Response(text='duplicate')
  if not self._reserve(p,eid,raw): return web.Response(status=202,text='duplicate or already processing')
  try:
   await self.bot.handle_payment_event(p,ev); self._done(p,eid); return web.Response(text='ok')
  except Exception as ex:
   self.bot.db.execute("UPDATE webhook_events SET state='failed',last_error=? WHERE provider=? AND event_id=?",(f'{type(ex).__name__}: {ex}'[:1000],p,eid))
   await self.bot.create_system_payment_ticket(p,ev,ex)
   return web.Response(status=500,text='processing failed; retry')
 async def stripe(self,req):
  raw=await req.read(); secret=os.getenv('STRIPE_WEBHOOK_SECRET',''); sig=req.headers.get('Stripe-Signature','')
  if not secret:return web.Response(status=503,text='not configured')
  try:
   import stripe
   ev=stripe.Webhook.construct_event(payload=raw,sig_header=sig,secret=secret,tolerance=300)
   ev=dict(ev)
  except Exception:return web.Response(status=400,text='invalid signature')
  return await self._process('stripe',ev,raw)
 async def paypal(self,req):
  raw=await req.read()
  try:ev=json.loads(raw)
  except Exception:return web.Response(status=400,text='invalid json')
  wid=os.getenv('PAYPAL_WEBHOOK_ID');cid=os.getenv('PAYPAL_CLIENT_ID');sec=os.getenv('PAYPAL_CLIENT_SECRET');sandbox=os.getenv('PAYPAL_SANDBOX','1')!='0';root='https://api-m.sandbox.paypal.com' if sandbox else 'https://api-m.paypal.com'
  if not all((wid,cid,sec)):return web.Response(status=503,text='not configured')
  import aiohttp
  try:
   async with aiohttp.ClientSession() as s:
    async with s.post(root+'/v1/oauth2/token',data={'grant_type':'client_credentials'},auth=aiohttp.BasicAuth(cid,sec)) as r:
     if r.status>=300:return web.Response(status=503,text='paypal auth failed')
     tok=(await r.json()).get('access_token')
    body={'auth_algo':req.headers.get('paypal-auth-algo'),'cert_url':req.headers.get('paypal-cert-url'),'transmission_id':req.headers.get('paypal-transmission-id'),'transmission_sig':req.headers.get('paypal-transmission-sig'),'transmission_time':req.headers.get('paypal-transmission-time'),'webhook_id':wid,'webhook_event':ev}
    async with s.post(root+'/v1/notifications/verify-webhook-signature',json=body,headers={'Authorization':f'Bearer {tok}'}) as r: verified=r.status<300 and (await r.json()).get('verification_status')=='SUCCESS'
  except Exception:return web.Response(status=503,text='paypal verification unavailable')
  if not verified:return web.Response(status=400,text='invalid signature')
  return await self._process('paypal',ev,raw)
