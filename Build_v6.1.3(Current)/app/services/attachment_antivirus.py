from __future__ import annotations
import os, shutil, subprocess
from pathlib import Path

FILE_SECURITY_NOTICE=(
    'Discord attachment scanning is an additional safety layer, not a guarantee. '
    'Users must maintain their own operating-system, browser, and antivirus protections, keep them updated, '
    'and avoid opening unexpected or suspicious files. A no-detection result does not prove a file is harmless.'
)

class AttachmentAV:
 def __init__(self,db): self.db=db
 def settings(self,gid):
  r=self.db.one('SELECT * FROM attachment_av_settings WHERE guild_id=?',(gid,))
  return dict(r) if r else {'guild_id':gid,'enabled':0,'provider':'defender','executable_path':'','max_size_mb':100,'all_channels':1}
 def save(self,gid,enabled,provider='defender',executable_path='',max_size_mb=100,all_channels=True):
  self.db.execute('INSERT INTO attachment_av_settings(guild_id,enabled,provider,executable_path,max_size_mb,all_channels) VALUES(?,?,?,?,?,?) ON CONFLICT(guild_id) DO UPDATE SET enabled=excluded.enabled,provider=excluded.provider,executable_path=excluded.executable_path,max_size_mb=excluded.max_size_mb,all_channels=excluded.all_channels,updated_at=CURRENT_TIMESTAMP',(gid,1 if enabled else 0,provider,executable_path,int(max_size_mb),1 if all_channels else 0))
 def _defender_path(self,configured=''):
  if configured and Path(configured).is_file(): return configured
  candidates=[]
  pd=os.environ.get('ProgramData',r'C:\ProgramData')
  platform=Path(pd)/'Microsoft'/'Windows Defender'/'Platform'
  if platform.is_dir():
   for d in sorted(platform.iterdir(),reverse=True): candidates.append(d/'MpCmdRun.exe')
  candidates += [Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'Windows Defender'/'MpCmdRun.exe']
  return str(next((p for p in candidates if p.is_file()),''))
 def executable(self,gid):
  s=self.settings(gid); p=str(s.get('executable_path') or '').strip()
  if s.get('provider')=='clamav': return p or shutil.which('clamscan') or ''
  return self._defender_path(p)
 def configured(self,gid):
  s=self.settings(gid);return bool(s.get('enabled') and self.executable(gid))
 def test(self,gid):
  s=self.settings(gid);exe=self.executable(gid)
  if not s.get('enabled'): return False,'Attachment AV is disabled.'
  if not exe:return False,f'{s.get("provider","defender")} scanner executable was not found.'
  try:
   cmd=[exe,'--version'] if s.get('provider')=='clamav' else [exe,'-GetFiles']
   r=subprocess.run(cmd,capture_output=True,text=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   return True,f'{s.get("provider")} scanner found at {exe}'
  except Exception as e:return False,f'{type(e).__name__}: {e}'
 def scan_file(self,gid,path):
  s=self.settings(gid);exe=self.executable(gid);provider=s.get('provider','defender')
  if not s.get('enabled'):return {'verdict':'disabled','detail':'Attachment AV disabled','provider':provider}
  if not exe:return {'verdict':'scan_error','detail':f'{provider} executable not found','provider':provider}
  try:
   if provider=='clamav':
    r=subprocess.run([exe,'--no-summary',str(path)],capture_output=True,text=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));out=((r.stdout or '')+'\n'+(r.stderr or '')).strip()
    verdict='no_detections' if r.returncode==0 else ('malicious' if r.returncode==1 else 'scan_error')
   else:
    r=subprocess.run([exe,'-Scan','-ScanType','3','-File',str(path),'-DisableRemediation'],capture_output=True,text=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));out=((r.stdout or '')+'\n'+(r.stderr or '')).strip();low=out.lower()
    threat_words=('threat detected','found threat','virus detected','malware detected')
    verdict='malicious' if any(x in low for x in threat_words) else ('no_detections' if r.returncode==0 else 'scan_error')
   return {'verdict':verdict,'detail':out[-1800:] or f'exit code {r.returncode}','provider':provider}
  except subprocess.TimeoutExpired:return {'verdict':'scan_error','detail':'Scanner timed out','provider':provider}
  except Exception as e:return {'verdict':'scan_error','detail':f'{type(e).__name__}: {e}','provider':provider}
 def record(self,gid,user_id,channel_id,message_id,filename,size,result):
  self.db.execute('INSERT INTO attachment_av_events(guild_id,user_id,channel_id,message_id,filename,size_bytes,provider,verdict,detail) VALUES(?,?,?,?,?,?,?,?,?)',(gid,user_id,channel_id,message_id,filename,size,result.get('provider',''),result.get('verdict','unknown'),result.get('detail','')[:2000]))
