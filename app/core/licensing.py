from __future__ import annotations
import hashlib,hmac,os,secrets,string
_ALPHABET='ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
def _secret()->bytes:
 value=(os.getenv('LICENSE_SIGNING_SECRET') or os.getenv('VAULT_API_KEY') or '').strip()
 if len(value)<32: raise RuntimeError('LICENSE_SIGNING_SECRET/VAULT_API_KEY missing or too short (32+ chars).')
 return value.encode()
def make_license_code()->str:
 serial=''.join(secrets.choice(_ALPHABET) for _ in range(12))
 return '420V-'+'-'.join(serial[i:i+4] for i in range(0,12,4))
def license_signature(code:str)->str:
 return hmac.new(_secret(),code.strip().upper().encode('ascii'),hashlib.sha256).hexdigest()
def verify_license_signature(code:str,stored_signature:str|None=None)->bool:
 try:
  c=code.strip().upper();parts=c.split('-')
  if stored_signature is None:return False
  valid_new=(len(parts)==4 and parts[0]=='420V' and all(len(x)==4 for x in parts[1:]) and all(ch in _ALPHABET for ch in ''.join(parts[1:])))
  # Pre-v3.4 database licenses remain verifiable after migration, while every newly issued key uses the short format.
  if not valid_new and not c.startswith('420V-'):return False
  return hmac.compare_digest(stored_signature,license_signature(c))
 except Exception:return False
