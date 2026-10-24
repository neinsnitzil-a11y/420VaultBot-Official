from __future__ import annotations
import json, os
from pathlib import Path
from cryptography.fernet import Fernet

class SMTPSettings:
    def __init__(self, bot):
        self.bot=bot; self.db=bot.db
        root=Path(__file__).resolve().parents[2]
        self.key_path=root/'data'/'smtp_secret.key'
        self.key_path.parent.mkdir(parents=True,exist_ok=True)
    def _fernet(self):
        if not self.key_path.exists():
            self.key_path.write_bytes(Fernet.generate_key())
            try: os.chmod(self.key_path,0o600)
            except OSError: pass
        return Fernet(self.key_path.read_bytes().strip())
    def get(self,gid):
        r=self.db.one('SELECT * FROM smtp_settings WHERE guild_id=?',(gid,))
        if not r:return None
        d=dict(r)
        try:d['password']=self._fernet().decrypt(d['password_enc'].encode()).decode()
        except Exception:d['password']=''
        return d
    def configured(self,gid):
        r=self.db.one('SELECT enabled,tested_at FROM smtp_settings WHERE guild_id=?',(gid,))
        return bool(r and r['enabled'] and r['tested_at'])
    def save(self,gid,host,port,username,password,from_email,from_name,security):
        security=security.upper().strip()
        if security not in ('STARTTLS','SSL'):raise ValueError('Security must be STARTTLS or SSL.')
        if not host.strip() or not from_email.strip() or '@' not in from_email:raise ValueError('SMTP host and a valid From Email are required.')
        port=int(port)
        if not 1<=port<=65535:raise ValueError('SMTP port must be 1-65535.')
        old=self.get(gid)
        if not password and old: password=old.get('password','')
        if username and not password:raise ValueError('SMTP password/app password is required when a username is used.')
        enc=self._fernet().encrypt(password.encode()).decode() if password else ''
        self.db.execute('INSERT INTO smtp_settings(guild_id,host,port,username,password_enc,from_email,from_name,security,enabled,tested_at,updated_at) VALUES(?,?,?,?,?,?,?,?,0,NULL,CURRENT_TIMESTAMP) ON CONFLICT(guild_id) DO UPDATE SET host=excluded.host,port=excluded.port,username=excluded.username,password_enc=excluded.password_enc,from_email=excluded.from_email,from_name=excluded.from_name,security=excluded.security,enabled=0,tested_at=NULL,updated_at=CURRENT_TIMESTAMP',(gid,host.strip(),port,username.strip(),enc,from_email.strip(),from_name.strip() or '420Vault Security',security))
    def mark_tested(self,gid):
        self.db.execute("UPDATE smtp_settings SET enabled=1,tested_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE guild_id=?",(gid,))
