from pathlib import Path
import getpass,json,urllib.request,urllib.error,secrets,subprocess,shutil,zipfile,tempfile
ROOT=Path(__file__).resolve().parent
env=ROOT/'.env'

def saved_token():
 if not env.exists():return ''
 for line in env.read_text(encoding='utf-8',errors='ignore').splitlines():
  if line.startswith('DISCORD_TOKEN='):return line.split('=',1)[1].strip().strip('"').strip("'")
 return ''
def valid_token(token):
 if not token:return False
 req=urllib.request.Request('https://discord.com/api/v10/users/@me',headers={'Authorization':'Bot '+token,'User-Agent':'420VaultBot/2'})
 try:
  with urllib.request.urlopen(req,timeout=10) as r:return r.status==200
 except urllib.error.HTTPError as e:return False if e.code in (401,403) else True
 except Exception:
  # If Discord cannot be reached, let discord.py report the network problem rather than discarding a possibly valid token.
  return True

def set_env_value(key,value):
 lines=env.read_text(encoding="utf-8",errors="ignore").splitlines() if env.exists() else []
 out=[]; found=False
 for line in lines:
  if line.startswith(key+"="):
   out.append(key+"="+value); found=True
  else: out.append(line)
 if not found: out.append(key+"="+value)
 env.write_text("\n".join(out).rstrip()+"\n",encoding="utf-8")

def get_env_value(key):
 if not env.exists(): return ""
 for line in env.read_text(encoding="utf-8",errors="ignore").splitlines():
  if line.startswith(key+"="): return line.split("=",1)[1].strip().strip(chr(34)).strip(chr(39))
 return ""

def bootstrap_link_security():
 tools=ROOT/'tools';dest=tools/'URLhaus';tools.mkdir(parents=True,exist_ok=True)
 if not dest.exists():
  print('Setting up Link Antivirus reference tooling (official abuse.ch URLhaus GitHub)...')
  git=shutil.which('git')
  if git:
   try:subprocess.run([git,'clone','--depth','1','https://github.com/abusech/URLhaus.git',str(dest)],check=True,timeout=120);print('URLhaus GitHub tooling installed.')
   except Exception as e:print('Git clone failed; trying GitHub ZIP fallback:',e)
  if not dest.exists():
   try:
    z=tools/'URLhaus-master.zip';urllib.request.urlretrieve('https://github.com/abusech/URLhaus/archive/refs/heads/master.zip',z)
    with zipfile.ZipFile(z) as a:a.extractall(tools)
    extracted=tools/'URLhaus-master'
    if extracted.exists():extracted.rename(dest)
    z.unlink(missing_ok=True);print('URLhaus GitHub tooling installed from ZIP.')
   except Exception as e:print('URLhaus reference tooling could not be downloaded. API integration can still be configured later in 420_admin:',e)
 key=get_env_value('URLHAUS_AUTH_KEY')
 if not key:
  print('\nOptional Link Antivirus setup: URLhaus requires a free Auth-Key from https://auth.abuse.ch/.')
  print('Press Enter to skip now; you can configure it later in 420_admin > Security.')
  try:key=getpass.getpass('URLhaus Auth-Key (hidden, optional): ').strip()
  except Exception:key=''
  if key:set_env_value('URLHAUS_AUTH_KEY',key);print('URLhaus Auth-Key saved locally. Link AV will be available to guilds by default.')
 return dest.exists()

def ensure_secrets():
 signing=get_env_value("LICENSE_SIGNING_SECRET")
 api=get_env_value("VAULT_API_KEY")
 if len(signing)<32:
  signing=secrets.token_urlsafe(64);set_env_value("LICENSE_SIGNING_SECRET",signing)
 if len(api)<32:
  api=secrets.token_urlsafe(64);set_env_value("VAULT_API_KEY",api)
 print("\n420Vault signing and website API secrets are configured separately.")
 print("For Base44, use the VAULT_API_KEY value as VAULT_API_SECRET.")
 print("Never use or expose LICENSE_SIGNING_SECRET as the website bearer credential.\n")
 return signing,api

ensure_secrets()
bootstrap_link_security()

token=saved_token()
if token and not valid_token(token):
 print('\nSaved Discord token was rejected. You will be asked for a new token.\n');token=''
while not token:
 print('420Vault - Bot Token Setup')
 print('Only the bot token is entered here. Server setup is done later with 420_setup in Discord.\n')
 token=getpass.getpass('Paste Discord BOT token (hidden): ').strip()
 if not token:continue
 if not valid_token(token):
  print('That token was rejected by Discord. Copy the token from Developer Portal > Bot, then try again.\n');token='';continue
 set_env_value('DISCORD_TOKEN',token);print('Token saved locally. Starting 420VaultBot...\n')
from app.bot import run
run()
