from __future__ import annotations
import json, logging, os, platform, threading, time
from pathlib import Path

log=logging.getLogger(__name__)

class HeartbeatWatchdog:
    """Independent OS thread monitoring bot liveness.

    On Windows, optionally requests that the SYSTEM stay awake while allowing the
    display to turn off. This does not defeat hibernation, lid-close policies,
    shutdowns, or loss of power/network.
    """
    def __init__(self, bot, state_path:Path):
        self.bot=bot; self.state_path=Path(state_path); self.stop_event=threading.Event()
        self.interval=max(10,int(os.getenv('HEARTBEAT_INTERVAL_SECONDS','30') or 30))
        self.prevent_sleep=os.getenv('HEARTBEAT_PREVENT_SYSTEM_SLEEP','1').lower() not in ('0','false','no','off')
        self.thread=None; self.started_at=time.time(); self.beats=0; self.last_ok=0.0; self.last_latency=None
    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.thread=threading.Thread(target=self._run,name='420Vault-Heartbeat',daemon=True); self.thread.start()
        log.info('Independent heartbeat watchdog started (interval=%ss, prevent_sleep=%s)',self.interval,self.prevent_sleep)
    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive(): self.thread.join(timeout=3)
        self._windows_allow_sleep()
    def snapshot(self):
        age=(time.time()-self.last_ok) if self.last_ok else None
        return {'thread_alive':bool(self.thread and self.thread.is_alive()),'beats':self.beats,'last_ok_age_seconds':age,'latency_ms':self.last_latency,'interval_seconds':self.interval,'prevent_sleep':self.prevent_sleep,'uptime_seconds':time.time()-self.started_at}
    def _windows_keep_awake(self):
        if platform.system()!='Windows' or not self.prevent_sleep:return
        try:
            import ctypes
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED. Deliberately omit ES_DISPLAY_REQUIRED,
            # so the laptop/monitor screen is free to switch off.
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
        except Exception: log.exception('Unable to request Windows system-awake state')
    def _windows_allow_sleep(self):
        if platform.system()!='Windows' or not self.prevent_sleep:return
        try:
            import ctypes; ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        except Exception: pass
    def _write_state(self,healthy,latency):
        self.state_path.parent.mkdir(parents=True,exist_ok=True)
        data={'pid':os.getpid(),'timestamp':time.time(),'healthy':healthy,'latency_ms':latency,'beats':self.beats}
        tmp=self.state_path.with_suffix('.tmp'); tmp.write_text(json.dumps(data),encoding='utf-8'); tmp.replace(self.state_path)
    def _run(self):
        self._windows_keep_awake()
        while not self.stop_event.is_set():
            try:
                ready=bool(self.bot.is_ready() and not self.bot.is_closed())
                latency=float(self.bot.latency*1000) if ready and self.bot.latency == self.bot.latency else None
                self.beats+=1; self.last_latency=latency
                if ready:self.last_ok=time.time()
                self._write_state(ready,latency)
            except Exception: log.exception('Heartbeat watchdog iteration failed')
            self.stop_event.wait(self.interval)
