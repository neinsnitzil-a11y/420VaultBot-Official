from __future__ import annotations
import os,json,hashlib
from urllib.parse import urlencode
import aiohttp
class PaymentError(Exception):pass
class PaymentService:
 def __init__(self,bot):self.bot=bot;self.db=bot.db
 def settings(self,gid,provider):
  r=self.db.one('SELECT * FROM payment_settings WHERE guild_id=? AND provider=?',(gid,provider));return ({'enabled':bool(r['enabled']),**json.loads(r['config_json'])} if r else {'enabled':False})
 def save_settings(self,gid,provider,enabled,config):self.db.execute('INSERT INTO payment_settings(guild_id,provider,enabled,config_json) VALUES(?,?,?,?) ON CONFLICT(guild_id,provider) DO UPDATE SET enabled=excluded.enabled,config_json=excluded.config_json',(gid,provider,1 if enabled else 0,json.dumps(config)))
 async def stripe_checkout(self,gid,uid,plan):
  key=os.getenv('STRIPE_SECRET_KEY');wh=os.getenv('STRIPE_WEBHOOK_SECRET')
  if not key:raise PaymentError('STRIPE_SECRET_KEY is not configured.')
  price=plan['stripe_price_id']
  if not price:raise PaymentError('This plan needs a Stripe Price ID in the plan configuration.')
  mode='payment' if plan['lifetime'] else 'subscription';base=os.getenv('PAYMENT_RETURN_URL','https://discord.com/app')
  data=[('mode',mode),('success_url',base),('cancel_url',base),('client_reference_id',f'{gid}:{uid}:{plan["id"]}'),('metadata[guild_id]',str(gid)),('metadata[user_id]',str(uid)),('metadata[plan_id]',str(plan['id'])),('line_items[0][price]',price),('line_items[0][quantity]','1')]
  async with aiohttp.ClientSession() as s:
   async with s.post('https://api.stripe.com/v1/checkout/sessions',data=data,auth=aiohttp.BasicAuth(key,'')) as r:
    x=await r.json()
    if r.status>=300:raise PaymentError(x.get('error',{}).get('message','Stripe checkout failed'))
    return x['url'],x['id']
 async def paypal_checkout(self,gid,uid,plan):
  cid=os.getenv('PAYPAL_CLIENT_ID');sec=os.getenv('PAYPAL_CLIENT_SECRET');sandbox=os.getenv('PAYPAL_SANDBOX','1')!='0';root='https://api-m.sandbox.paypal.com' if sandbox else 'https://api-m.paypal.com'
  if not cid or not sec:raise PaymentError('PAYPAL_CLIENT_ID/PAYPAL_CLIENT_SECRET are not configured.')
  if not plan['paypal_plan_id']:raise PaymentError('This plan needs a PayPal Plan ID.')
  async with aiohttp.ClientSession() as s:
   async with s.post(root+'/v1/oauth2/token',data={'grant_type':'client_credentials'},auth=aiohttp.BasicAuth(cid,sec)) as r:tok=(await r.json()).get('access_token')
   if not tok:raise PaymentError('PayPal authentication failed.')
   body={'plan_id':plan['paypal_plan_id'],'custom_id':f'{gid}:{uid}:{plan["id"]}','application_context':{'user_action':'SUBSCRIBE_NOW'}}
   async with s.post(root+'/v1/billing/subscriptions',json=body,headers={'Authorization':f'Bearer {tok}','Content-Type':'application/json'}) as r:
    x=await r.json()
    if r.status>=300:raise PaymentError(x.get('message','PayPal checkout failed'))
    link=next((a['href'] for a in x.get('links',[]) if a.get('rel')=='approve'),None)
    if not link:raise PaymentError('PayPal did not return an approval URL.')
    return link,x['id']


 async def paypal_billing_period_end(self,subid):
  cid=os.getenv('PAYPAL_CLIENT_ID');sec=os.getenv('PAYPAL_CLIENT_SECRET');sandbox=os.getenv('PAYPAL_SANDBOX','1')!='0';root='https://api-m.sandbox.paypal.com' if sandbox else 'https://api-m.paypal.com'
  if not all((cid,sec,subid)):raise PaymentError('PayPal subscription lookup is not configured.')
  async with aiohttp.ClientSession() as sess:
   async with sess.post(root+'/v1/oauth2/token',data={'grant_type':'client_credentials'},auth=aiohttp.BasicAuth(cid,sec)) as rr:tok=(await rr.json()).get('access_token')
   if not tok:raise PaymentError('PayPal authentication failed.')
   async with sess.get(root+'/v1/billing/subscriptions/'+subid,headers={'Authorization':f'Bearer {tok}'}) as rr:
    data=await rr.json()
    if rr.status>=300:raise PaymentError(data.get('message','PayPal subscription lookup failed'))
  end=(data.get('billing_info') or {}).get('next_billing_time')
  if not end:raise PaymentError('PayPal did not return next_billing_time.')
  return end

 # Reconcile a provider transaction without trusting the Discord client.
 async def reconcile_transaction(self,t):
  provider=t.get('provider'); subid=None
  if t.get('subscription_id'):
   s=self.db.one('SELECT provider_subscription_id FROM subscriptions WHERE id=?',(t['subscription_id'],));subid=s['provider_subscription_id'] if s else None
  if provider=='stripe':
   import stripe
   stripe.api_key=os.getenv('STRIPE_SECRET_KEY')
   if not stripe.api_key:return 'not_configured'
   try:
    if subid:return str(stripe.Subscription.retrieve(subid).status)
    obj=stripe.checkout.Session.retrieve(t.get('provider_transaction_id'));return str(obj.status)
   except Exception as ex:return 'error:'+type(ex).__name__
  if provider=='paypal':
   cid=os.getenv('PAYPAL_CLIENT_ID');sec=os.getenv('PAYPAL_CLIENT_SECRET');sandbox=os.getenv('PAYPAL_SANDBOX','1')!='0';root='https://api-m.sandbox.paypal.com' if sandbox else 'https://api-m.paypal.com'
   if not all((cid,sec,subid)):return 'not_configured_or_unlinked'
   import aiohttp
   try:
    async with aiohttp.ClientSession() as s:
     async with s.post(root+'/v1/oauth2/token',data={'grant_type':'client_credentials'},auth=aiohttp.BasicAuth(cid,sec)) as r:tok=(await r.json()).get('access_token')
     async with s.get(root+'/v1/billing/subscriptions/'+subid,headers={'Authorization':f'Bearer {tok}'}) as r:return str((await r.json()).get('status','unknown')).lower()
   except Exception as ex:return 'error:'+type(ex).__name__
  return t.get('status','unknown')
