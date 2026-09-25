"""Small external health probe for Task Scheduler/Uptime monitors. No third-party packages required."""
import os, sys, urllib.request
host=os.getenv('HEALTHCHECK_URL',f"http://127.0.0.1:{os.getenv('WEBHOOK_PORT','8420')}/health")
try:
    with urllib.request.urlopen(host,timeout=8) as r:
        body=r.read(4096).decode('utf-8','replace')
        if r.status != 200: raise RuntimeError(f'HTTP {r.status}')
        print(body)
except Exception as exc:
    print(f'420Vault healthcheck failed: {exc}',file=sys.stderr)
    raise SystemExit(1)
