from __future__ import annotations
import asyncio, hashlib, html, os, time
from aiohttp import web

def esc(v): return html.escape(str(v),quote=True)
def base(): return os.getenv('AUTH_PUBLIC_BASE_URL','').rstrip('/')
def page(title,body):
    doc='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+esc(title)+'</title><style>body{font-family:system-ui;background:#101214;color:#eee;max-width:560px;margin:5vh auto;padding:24px}.card{background:#191d20;padding:24px;border-radius:16px}input,button{width:100%;box-sizing:border-box;padding:12px;margin:7px 0;border-radius:9px;border:1px solid #444;background:#0f1113;color:#fff}button{background:#2d6cdf;border:0;font-weight:700}a{color:#7fb0ff}.err{color:#ff8c8c}.ok{color:#8cffaa}small{color:#aaa}</style></head><body><div class="card"><h2>'+esc(title)+'</h2>'+body+'</div></body></html>'
    return web.Response(text=doc,content_type='text/html',headers={'Cache-Control':'no-store','X-Frame-Options':'DENY','Content-Security-Policy':"default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",'Referrer-Policy':'no-referrer'})
def login_form(ch,msg=''):
    m='<p class="err">'+esc(msg)+'</p>' if msg else ''
    return m+'<form method="post"><input type="hidden" name="challenge" value="'+esc(ch)+'"><input name="username" autocomplete="username" placeholder="Username" required><input name="password" type="password" autocomplete="current-password" placeholder="Password" required><input name="twofa" inputmode="numeric" autocomplete="one-time-code" placeholder="2FA code (if enabled)"><button>Sign in</button></form><hr><h3>First time?</h3><form method="post" action="/auth/register"><input type="hidden" name="challenge" value="'+esc(ch)+'"><input name="username" placeholder="Username" required><input name="email" type="email" placeholder="Recovery email you control" required><input name="password" type="password" autocomplete="new-password" placeholder="Password (12+ chars)" required><button>Create account</button></form><p><a href="/auth/forgot">Forgot password?</a></p><small>Never enter your Discord password here. This is a separate 420VaultBot account bound to your Discord ID.</small>'
class AuthWeb:
    def __init__(self,bot): self.bot=bot; self.auth=bot.auth; self.fail={}
    def register(self,app):
        app.router.add_get('/auth',self.login_get); app.router.add_post('/auth',self.login_post); app.router.add_post('/auth/register',self.register_post); app.router.add_get('/auth/verify',self.verify); app.router.add_get('/auth/forgot',self.forgot_get); app.router.add_post('/auth/forgot',self.forgot_post); app.router.add_get('/auth/reset',self.reset_get); app.router.add_post('/auth/reset',self.reset_post)
    def limited(self,req):
        ip=req.remote or 'unknown'; now=time.time(); xs=[x for x in self.fail.get(ip,[]) if now-x<900]; self.fail[ip]=xs; return len(xs)>=8
    def bad(self,req): self.fail.setdefault(req.remote or 'unknown',[]).append(time.time())
    async def login_get(self,req):
        ch=req.query.get('c',''); return page('420VaultBot Sign In',login_form(ch,'This sign-in link is invalid or expired.') if not self.auth.challenge(ch) else login_form(ch))
    async def login_post(self,req):
        if self.limited(req): raise web.HTTPTooManyRequests(text='Too many attempts. Try again later.')
        d=await req.post(); ch=d.get('challenge',''); c=self.auth.challenge(ch)
        if not c:return page('420VaultBot Sign In',login_form(ch,'Sign-in link expired. Request a new one from Discord.'))
        from app.services.auth import AccountLocked,TwoFactorRequired,TwoFactorInvalid
        try:a=self.auth.verify_login(c['guild_id'],c['user_id'],d.get('username',''),d.get('password',''),d.get('twofa',''))
        except AccountLocked as e:
            mins=max(1,(e.until-int(time.time())+59)//60)
            return page('420VaultBot Sign In','<p class="err">Account temporarily locked after repeated failed sign-in attempts. Try again in about '+esc(mins)+' minute(s), or use Forgot Password.</p>')
        except TwoFactorRequired as e:return page('Two-factor code required',login_form(ch,str(e)))
        except TwoFactorInvalid as e:
            self.bad(req); state=self.auth.record_login_failure(c['guild_id'],c['user_id'])
            if state.get('locked'): return page('420VaultBot Sign In','<p class="err">Account temporarily locked after repeated failed sign-in attempts. All active sessions were signed out.</p>')
            return page('420VaultBot Sign In',login_form(ch,str(e)))
        except PermissionError as e:return page('Email verification required','<p class="err">'+esc(e)+'</p>')
        if not a:
            self.bad(req); state=self.auth.record_login_failure(c['guild_id'],c['user_id'])
            if state.get('locked'):
                acct=state.get('account'); mins=max(1,(int(state.get('lock_until') or 0)-int(time.time())+59)//60)
                if state.get('new_lock') and acct:
                    reset_url=base()+'/auth/forgot'
                    body=('Security alert: your 420VaultBot account was temporarily locked after 3 unsuccessful sign-in attempts.\n\n'
                          f'Lock duration: about {mins} minutes.\n'
                          'All active 420Vault sessions were revoked.\n\n'
                          'If this was not you, reset your password here:\n'+reset_url+'\n\n'
                          'Never share your 420VaultBot or Discord password.')
                    asyncio.create_task(self.auth.send_email(acct['email'],'420VaultBot security alert: account temporarily locked',body))
                return page('420VaultBot Sign In','<p class="err">Account temporarily locked after repeated failed sign-in attempts. All active sessions were signed out. Check your recovery email or use Forgot Password.</p>')
            return page('420VaultBot Sign In',login_form(ch,'Invalid username or password.'))
        self.auth.create_session(c['guild_id'],c['user_id']); self.auth.consume_challenge(ch); self.bot.db.audit(c['guild_id'],c['user_id'],'auth_login','420Vault session started')
        return page('Signed in','<p class="ok">✅ Session active. Return to Discord.</p><p>You will be signed out after 10 minutes without using 420VaultBot.</p>')
    async def register_post(self,req):
        if self.limited(req): raise web.HTTPTooManyRequests(text='Too many attempts. Try again later.')
        d=await req.post(); ch=d.get('challenge',''); c=self.auth.challenge(ch)
        if not c:return page('Registration expired','<p class="err">Request a new sign-in link from Discord.</p>')
        if self.auth.account(c['guild_id'],c['user_id']):return page('Account already exists','<p>Use Sign In or Forgot Password.</p>')
        try:t=self.auth.register(c['guild_id'],c['user_id'],d.get('username',''),d.get('email',''),d.get('password',''))
        except ValueError as e:return page('Create account',login_form(ch,str(e)))
        a=self.auth.account(c['guild_id'],c['user_id']); url=base()+'/auth/verify?t='+t
        try:await self.auth.send_email(a['email'],'Verify your 420VaultBot account','Verify your 420VaultBot account:\n\n'+url+'\n\nThis link expires in 15 minutes.')
        except Exception:return page('Email configuration error','<p class="err">Account created, but verification email could not be sent. Ask the bot owner to configure SMTP.</p>')
        return page('Check your email','<p class="ok">Verification sent. Open the link, then return to Discord and sign in.</p>')
    async def verify(self,req):
        r=self.auth.consume_email_token(req.query.get('t',''),'verify_email')
        if not r:return page('Invalid link','<p class="err">Verification link is invalid or expired.</p>')
        self.bot.db.execute('UPDATE auth_accounts SET email_verified=1,updated_at=? WHERE guild_id=? AND discord_user_id=?',(int(time.time()),r['guild_id'],r['user_id'])); return page('Email verified','<p class="ok">✅ Email verified. Return to Discord and request a sign-in link.</p>')
    async def forgot_get(self,req): return page('Reset password','<form method="post"><input name="email" type="email" placeholder="Registered recovery email" required><button>Send reset link</button></form>')
    async def forgot_post(self,req):
        d=await req.post(); email=d.get('email','').strip().lower(); accounts=self.bot.db.all('SELECT * FROM auth_accounts WHERE lower(email)=lower(?)',(email,))
        for a in accounts:
            t=self.auth.issue_email_token(a['guild_id'],a['discord_user_id'],'password_reset',900); url=base()+'/auth/reset?t='+t
            try:await self.auth.send_email(a['email'],'Reset your 420VaultBot password','Reset your password:\n\n'+url+'\n\nThis one-use link expires in 15 minutes.')
            except Exception:pass
        return page('Reset password','<p>If an account exists for that email, a reset message has been sent.</p>')
    async def reset_get(self,req):
        t=req.query.get('t',''); r=self.bot.db.one('SELECT 1 FROM auth_tokens WHERE token_hash=? AND kind=? AND used_at IS NULL AND expires_at>?',(hashlib.sha256(t.encode()).hexdigest(),'password_reset',int(time.time()))) if t else None
        if not r:return page('Invalid link','<p class="err">Reset link is invalid or expired.</p>')
        return page('Choose new password','<form method="post"><input type="hidden" name="token" value="'+esc(t)+'"><input type="password" name="password" autocomplete="new-password" placeholder="New password" required><button>Reset password</button></form>')
    async def reset_post(self,req):
        from app.services.auth import PH,validate_password
        d=await req.post(); r=self.auth.consume_email_token(d.get('token',''),'password_reset')
        if not r:return page('Invalid link','<p class="err">Reset link is invalid or expired.</p>')
        try:validate_password(d.get('password',''))
        except ValueError as e:return page('Password rejected','<p class="err">'+esc(e)+'</p>')
        self.bot.db.execute('UPDATE auth_accounts SET password_hash=?,failed_login_count=0,lock_until=0,last_failed_at=NULL,updated_at=? WHERE guild_id=? AND discord_user_id=?',(PH.hash(d.get('password','')),int(time.time()),r['guild_id'],r['user_id'])); self.auth.revoke(r['guild_id'],r['user_id']); self.bot.db.execute('DELETE FROM auth_challenges WHERE guild_id=? AND user_id=?',(r['guild_id'],r['user_id'])); self.bot.db.audit(r['guild_id'],r['user_id'],'auth_password_reset','password reset; lock cleared; sessions/challenges revoked'); return page('Password reset','<p class="ok">✅ Password changed. Account lock cleared and all sessions were signed out. Return to Discord to sign in.</p>')
