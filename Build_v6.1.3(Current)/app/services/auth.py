from __future__ import annotations
import asyncio, base64, hashlib, hmac, json, os, secrets, smtplib, ssl, struct, time, re
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import quote
from cryptography.fernet import Fernet
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
PH=PasswordHasher(time_cost=3,memory_cost=65536,parallelism=2,hash_len=32,salt_len=16)
IDLE_SECONDS=600
MAX_LOGIN_FAILURES=3
LOCK_SECONDS=max(60,int(os.getenv('AUTH_LOCK_SECONDS','1800')))

class AccountLocked(PermissionError):
    def __init__(self, until):
        self.until=int(until); super().__init__('Account temporarily locked.')

class TwoFactorRequired(PermissionError):
    pass

class TwoFactorInvalid(PermissionError):
    pass
def _hash_token(v): return hashlib.sha256(v.encode()).hexdigest()
def _now(): return int(time.time())
def validate_password(p):
    if len(p)<12: raise ValueError('Password must be at least 12 characters.')
    if len(p)>128: raise ValueError('Password is too long.')
    if not any(c.islower() for c in p) or not any(c.isupper() for c in p) or not any(c.isdigit() for c in p): raise ValueError('Password needs uppercase, lowercase and a number.')
class AuthService:
    def __init__(self,bot):
        self.bot=bot; self.db=bot.db
        root=Path(__file__).resolve().parents[2]
        self._twofa_key_path=root/'data'/'auth_2fa_secret.key'
        self._twofa_key_path.parent.mkdir(parents=True,exist_ok=True)
    def _twofa_fernet(self):
        if not self._twofa_key_path.exists():
            self._twofa_key_path.write_bytes(Fernet.generate_key())
            try: os.chmod(self._twofa_key_path,0o600)
            except OSError: pass
        return Fernet(self._twofa_key_path.read_bytes().strip())
    def _enc2fa(self,value): return self._twofa_fernet().encrypt(value.encode()).decode() if value else ''
    def _dec2fa(self,value):
        if not value:return ''
        try:return self._twofa_fernet().decrypt(value.encode()).decode()
        except Exception:return ''
    @staticmethod
    def _totp(secret, for_time=None):
        when=int(time.time() if for_time is None else for_time); counter=when//30
        key=base64.b32decode(secret.upper()+'='*((8-len(secret)%8)%8))
        digest=hmac.new(key,struct.pack('>Q',counter),hashlib.sha1).digest()
        off=digest[-1]&15; num=(struct.unpack('>I',digest[off:off+4])[0]&0x7fffffff)%1000000
        return f'{num:06d}'
    def _verify_totp(self,secret,code):
        code=(code or '').strip().replace(' ','')
        if not re.fullmatch(r'\d{6}',code):return False
        now=int(time.time())
        return any(hmac.compare_digest(self._totp(secret,now+(step*30)),code) for step in (-1,0,1))
    def twofa_enabled(self,gid,uid):
        r=self.account(gid,uid);return bool(r and r['totp_enabled'])
    def begin_twofa_setup(self,gid,uid):
        r=self.account(gid,uid)
        if not r:raise ValueError('Create a 420Vault account first.')
        if not r['email_verified']:raise PermissionError('Verify your recovery email before enabling 2FA.')
        if r['totp_enabled']:raise ValueError('Two-factor authentication is already enabled.')
        secret=base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
        self.db.execute('UPDATE auth_accounts SET totp_pending_enc=?,updated_at=? WHERE guild_id=? AND discord_user_id=?',(self._enc2fa(secret),_now(),gid,uid))
        issuer=quote('420VaultBot'); label=quote(f'420Vault:{r["username"]}')
        uri=f'otpauth://totp/{label}?secret={secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30'
        return secret,uri
    def confirm_twofa_setup(self,gid,uid,code):
        r=self.account(gid,uid)
        if not r:raise ValueError('Account not found.')
        secret=self._dec2fa(r['totp_pending_enc'])
        if not secret:raise ValueError('Start 2FA setup first.')
        if not self._verify_totp(secret,code):raise ValueError('Invalid authenticator code.')
        recovery=[f'{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}' for _ in range(8)]
        hashes=[_hash_token(x.replace('-','').upper()) for x in recovery]
        self.db.execute("UPDATE auth_accounts SET totp_secret_enc=?,totp_pending_enc='',totp_enabled=1,totp_recovery_hashes=?,updated_at=? WHERE guild_id=? AND discord_user_id=?",(self._enc2fa(secret),json.dumps(hashes),_now(),gid,uid))
        self.revoke(gid,uid)
        self.db.audit(gid,uid,'auth_2fa_enabled','TOTP 2FA enabled; sessions revoked')
        return recovery
    def verify_twofa(self,gid,uid,code,consume_recovery=True):
        r=self.account(gid,uid)
        if not r or not r['totp_enabled']:return True
        secret=self._dec2fa(r['totp_secret_enc'])
        raw=(code or '').strip()
        if secret and self._verify_totp(secret,raw):return True
        normalized=raw.replace('-','').replace(' ','').upper()
        try: hashes=json.loads(r['totp_recovery_hashes'] or '[]')
        except Exception: hashes=[]
        hv=_hash_token(normalized) if normalized else ''
        if hv and hv in hashes:
            if consume_recovery:
                hashes.remove(hv);self.db.execute('UPDATE auth_accounts SET totp_recovery_hashes=?,updated_at=? WHERE id=?',(json.dumps(hashes),_now(),r['id']))
                self.db.audit(gid,uid,'auth_2fa_recovery_used',f'recovery code used; {len(hashes)} remaining')
            return True
        return False
    def disable_twofa(self,gid,uid,code):
        r=self.account(gid,uid)
        if not r or not r['totp_enabled']:raise ValueError('2FA is not enabled.')
        if not self.verify_twofa(gid,uid,code,True):raise ValueError('Invalid authenticator or recovery code.')
        self.db.execute("UPDATE auth_accounts SET totp_secret_enc='',totp_pending_enc='',totp_enabled=0,totp_recovery_hashes='[]',updated_at=? WHERE guild_id=? AND discord_user_id=?",(_now(),gid,uid))
        self.revoke(gid,uid);self.db.audit(gid,uid,'auth_2fa_disabled','TOTP 2FA disabled; sessions revoked')
    def cleanup(self):
        now=_now(); self.db.execute('DELETE FROM auth_sessions WHERE expires_at<=? OR last_activity<=?',(now,now-IDLE_SECONDS)); self.db.execute('DELETE FROM auth_challenges WHERE expires_at<=?',(now,)); self.db.execute('DELETE FROM auth_tokens WHERE expires_at<=? OR used_at IS NOT NULL',(now,))
    def create_challenge(self,gid,uid,purpose='login'):
        self.cleanup(); raw=secrets.token_urlsafe(32); now=_now(); self.db.execute('INSERT INTO auth_challenges(token_hash,guild_id,user_id,purpose,created_at,expires_at) VALUES(?,?,?,?,?,?)',(_hash_token(raw),gid,uid,purpose,now,now+600)); return raw
    def challenge(self,raw): return self.db.one('SELECT * FROM auth_challenges WHERE token_hash=? AND expires_at>?',(_hash_token(raw),_now())) if raw else None
    def consume_challenge(self,raw): self.db.execute('DELETE FROM auth_challenges WHERE token_hash=?',(_hash_token(raw),))
    def account(self,gid,uid): return self.db.one('SELECT * FROM auth_accounts WHERE guild_id=? AND discord_user_id=?',(gid,uid))
    def register(self,gid,uid,username,email,password):
        username=username.strip(); email=email.strip().lower()
        if not re.fullmatch(r'[A-Za-z0-9_.-]{3,32}',username): raise ValueError('Username must be 3-32 characters using letters, numbers, . _ or -.')
        if '@' not in email or len(email)>254: raise ValueError('Enter a valid recovery email address.')
        validate_password(password); now=_now()
        try:
            self.db.execute('INSERT INTO auth_accounts(guild_id,discord_user_id,username,email,password_hash,email_verified,created_at,updated_at) VALUES(?,?,?,?,?,0,?,?)',(gid,uid,username,email,PH.hash(password),now,now))
        except Exception as e:
            if 'UNIQUE' in str(e).upper(): raise ValueError('That username/email is already registered for this server.')
            raise
        try:
            if hasattr(self.bot,'profiles'): self.bot.profiles.ensure(gid,uid)
        except Exception:
            pass
        return self.issue_email_token(gid,uid,'verify_email',900)
    def issue_email_token(self,gid,uid,kind,ttl=900):
        raw=secrets.token_urlsafe(40); now=_now(); self.db.execute('DELETE FROM auth_tokens WHERE guild_id=? AND user_id=? AND kind=?',(gid,uid,kind)); self.db.execute('INSERT INTO auth_tokens(token_hash,guild_id,user_id,kind,created_at,expires_at) VALUES(?,?,?,?,?,?)',(_hash_token(raw),gid,uid,kind,now,now+ttl)); return raw
    def consume_email_token(self,raw,kind):
        r=self.db.one('SELECT * FROM auth_tokens WHERE token_hash=? AND kind=? AND used_at IS NULL AND expires_at>?',(_hash_token(raw),kind,_now())) if raw else None
        if not r:return None
        self.db.execute('UPDATE auth_tokens SET used_at=? WHERE token_hash=?',(_now(),_hash_token(raw))); return r
    def consume_email_token_for(self,raw,kind,gid,uid):
        r=self.db.one('SELECT * FROM auth_tokens WHERE token_hash=? AND kind=? AND guild_id=? AND user_id=? AND used_at IS NULL AND expires_at>?',(_hash_token(raw),kind,gid,uid,_now())) if raw else None
        if not r:return None
        self.db.execute('UPDATE auth_tokens SET used_at=? WHERE token_hash=?',(_now(),_hash_token(raw))); return r
    def verify_login(self,gid,uid,username,password,twofa_code=None):
        # The challenge is already bound to this Discord user. Count failures on
        # that bound 420Vault account even when an attacker guesses a wrong username.
        r=self.account(gid,uid)
        if not r:return None
        now=_now(); lock_until=int(r['lock_until'] or 0)
        if lock_until>now: raise AccountLocked(lock_until)
        username_ok=(r['username'].lower()==username.strip().lower())
        password_ok=False
        if username_ok:
            try: password_ok=PH.verify(r['password_hash'],password)
            except (VerifyMismatchError,VerificationError): password_ok=False
        if not (username_ok and password_ok): return None
        if not r['email_verified']: raise PermissionError('Verify your recovery email before signing in.')
        if r['totp_enabled']:
            if not (twofa_code or '').strip(): raise TwoFactorRequired('Enter the 6-digit authenticator code or a recovery code.')
            if not self.verify_twofa(gid,uid,twofa_code,True): raise TwoFactorInvalid('Invalid authenticator or recovery code.')
        self.db.execute('UPDATE auth_accounts SET failed_login_count=0,lock_until=0,last_failed_at=NULL,updated_at=? WHERE id=?',(now,r['id']))
        if PH.check_needs_rehash(r['password_hash']): self.db.execute('UPDATE auth_accounts SET password_hash=?,updated_at=? WHERE id=?',(PH.hash(password),now,r['id']))
        return self.account(gid,uid)
    def record_login_failure(self,gid,uid):
        r=self.account(gid,uid)
        if not r:return {'count':0,'locked':False,'account':None,'lock_until':0}
        now=_now(); lock_until=int(r['lock_until'] or 0)
        if lock_until>now:return {'count':int(r['failed_login_count'] or 0),'locked':True,'account':r,'lock_until':lock_until}
        count=int(r['failed_login_count'] or 0)+1
        if count>=MAX_LOGIN_FAILURES:
            lock_until=now+LOCK_SECONDS
            self.db.execute('UPDATE auth_accounts SET failed_login_count=?,lock_until=?,last_failed_at=?,updated_at=? WHERE id=?',(count,lock_until,now,now,r['id']))
            # A lock is a security boundary: kill every session and every outstanding
            # Discord->web login challenge for this account immediately.
            self.revoke(gid,uid)
            self.db.execute('DELETE FROM auth_challenges WHERE guild_id=? AND user_id=?',(gid,uid))
            self.db.audit(gid,uid,'auth_account_locked',f'login failures={count}; lock_until={lock_until}; sessions/challenges revoked')
            return {'count':count,'locked':True,'account':self.account(gid,uid),'lock_until':lock_until,'new_lock':True}
        self.db.execute('UPDATE auth_accounts SET failed_login_count=?,last_failed_at=?,updated_at=? WHERE id=?',(count,now,now,r['id']))
        self.db.audit(gid,uid,'auth_login_failed',f'failed login {count}/{MAX_LOGIN_FAILURES}')
        return {'count':count,'locked':False,'account':self.account(gid,uid),'lock_until':0}
    def clear_login_lock(self,gid,uid):
        self.db.execute('UPDATE auth_accounts SET failed_login_count=0,lock_until=0,last_failed_at=NULL,updated_at=? WHERE guild_id=? AND discord_user_id=?',(_now(),gid,uid))
    def create_session(self,gid,uid):
        raw=secrets.token_urlsafe(40); now=_now(); self.db.execute('DELETE FROM auth_sessions WHERE guild_id=? AND user_id=?',(gid,uid)); self.db.execute('INSERT INTO auth_sessions(session_hash,guild_id,user_id,created_at,last_activity,expires_at) VALUES(?,?,?,?,?,?)',(_hash_token(raw),gid,uid,now,now,now+IDLE_SECONDS)); return raw
    def session_active(self,gid,uid,touch=True):
        now=_now(); r=self.db.one('SELECT * FROM auth_sessions WHERE guild_id=? AND user_id=? AND expires_at>? AND last_activity>? ORDER BY created_at DESC LIMIT 1',(gid,uid,now,now-IDLE_SECONDS))
        if not r:return False
        if touch:self.db.execute('UPDATE auth_sessions SET last_activity=?,expires_at=? WHERE session_hash=?',(now,now+IDLE_SECONDS,r['session_hash']))
        return True
    def revoke(self,gid,uid): self.db.execute('DELETE FROM auth_sessions WHERE guild_id=? AND user_id=?',(gid,uid))
    async def send_email(self,to,subject,body,gid=None):
        cfg=self.bot.smtp_settings.get(gid) if gid is not None and hasattr(self.bot,'smtp_settings') else None
        if cfg:
            host=cfg['host']; port=int(cfg['port']); user=cfg['username']; pwd=cfg['password']; sender=cfg['from_email']; from_name=cfg['from_name']; security=cfg['security']
        else:
            host=os.getenv('AUTH_SMTP_HOST','').strip(); port=int(os.getenv('AUTH_SMTP_PORT','587')); user=os.getenv('AUTH_SMTP_USER','').strip(); pwd=os.getenv('AUTH_SMTP_PASSWORD',''); sender=os.getenv('AUTH_FROM_EMAIL',user).strip(); from_name='420Vault Security'; security='SSL' if os.getenv('AUTH_SMTP_SSL','0')=='1' else 'STARTTLS'
        if not host or not sender: raise RuntimeError('SMTP is not configured')
        msg=EmailMessage(); msg['From']=f'{from_name} <{sender}>' if from_name else sender; msg['To']=to; msg['Subject']=subject; msg.set_content(body)
        def send():
            if security=='SSL':
                with smtplib.SMTP_SSL(host,port,context=ssl.create_default_context(),timeout=15) as s:
                    if user:s.login(user,pwd)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(host,port,timeout=15) as s:
                    s.ehlo(); s.starttls(context=ssl.create_default_context()); s.ehlo()
                    if user:s.login(user,pwd)
                    s.send_message(msg)
        await asyncio.to_thread(send)
