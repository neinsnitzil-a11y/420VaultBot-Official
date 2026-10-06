"""420VaultBot v6.4.0 conservative upgrader: dry-run, preflight and rollback.

Never copies user state from the distribution into the live installation.
Stop the existing bot before applying this update.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SOURCE_ROOTS = ('app', 'scripts', 'base44_reference')
ROOT_FILES = ('main.py', 'VERSION', 'requirements.txt', 'README.md', 'run.bat', 'run_forever.bat', 'run_420vault_watchdog.bat', 'install.bat', 'install_and_run.bat', 'setup_and_start.py')
SKIP_DIRS = {'.venv', '.git', 'data', 'logs', 'legacy', 'tests', '__pycache__', '.pytest_cache', 'backups', 'credentials', 'secrets'}
SKIP_NAMES = {'.env', '.env.local', '.env.production', 'config.json', 'settings.json', 'credentials.json', 'token.json', 'client_secret.json'}
SKIP_EXT = {'.db', '.sqlite', '.sqlite3', '.pem', '.key', '.p12', '.pfx'}
REQUIRED = ('app/bot.py', 'app/views/command_center.py', 'app/views/auth_native.py', 'app/views/user_profile.py', 'app/services/user_profiles.py', 'app/services/auth.py', 'app/core/database.py', 'app/views/admin.py', 'app/views/vault_browser.py', 'app/views/drive_browser.py', 'app/views/license.py', 'app/cogs/legacy_commands.py')

def version(root):
    file = root / 'VERSION'
    if file.is_file():
        val = file.read_text(encoding='utf8').strip()
        if re.fullmatch(r'\d+\.\d+\.\d+', val): return tuple(map(int, val.split('.')))
    file = root / 'app/version.py'
    if file.is_file():
        m = re.search(r"VERSION\s*=\s*['\"](\d+\.\d+\.\d+)['\"]", file.read_text(encoding='utf8'))
        if m: return tuple(map(int, m.group(1).split('.')))
    return None

def sources():
    entries = [ROOT / name for name in ROOT_FILES if (ROOT / name).is_file()]
    for folder in SOURCE_ROOTS:
        loc = ROOT / folder
        if loc.is_dir():
            entries.extend(p for p in loc.rglob('*') if p.is_file())
    return sorted([p for p in entries if not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and p.name not in SKIP_NAMES and p.suffix.lower() not in SKIP_EXT], key=lambda p: str(p))

def preflight(dst, allow_downgrade=False):
    if not dst.is_dir() or not (dst / 'app/bot.py').is_file(): raise ValueError('Destination must be an EXISTING 420VaultBot installation with app/bot.py.')
    if dst == ROOT or ROOT in dst.parents or dst in ROOT.parents: raise ValueError('Source/destination must be separate directories.')
    missing = [str(f) for f in REQUIRED if not (ROOT / f).is_file()]
    if missing: raise ValueError('Release missing protected modules: ' + ', '.join(missing))
    incoming, old = version(ROOT), version(dst)
    if incoming is None: raise ValueError('Invalid incoming release version.')
    if old is not None and old > incoming and not allow_downgrade: raise ValueError(f'Refusing version downgrade {old} -> {incoming}. Pass --allow-downgrade only for intentional rollbacks.')
    return old, incoming

def replace_with_rollback(dst, changes, backup):
    backed_up = []
    installed = []
    try:
        for src, rel in changes:
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                dest = backup / 'overwritten' / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, dest)
                backed_up.append((dest, target))
            else:
                installed.append(target)
            # Copy into the same filesystem and replace only after copy completed.
            fd, tmp = tempfile.mkstemp(prefix='.420vault-', dir=target.parent)
            os.close(fd)
            try:
                shutil.copy2(src, tmp)
                os.replace(tmp, target)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
    except Exception:
        for target in reversed(installed):
            try: target.unlink(missing_ok=True)
            except OSError: pass
        for saved, target in reversed(backed_up):
            shutil.copy2(saved, target)
        raise

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', help='Existing installation directory')
    parser.add_argument('--dry-run', action='store_true', help='Show actions without modifying installation')
    parser.add_argument('--allow-downgrade', action='store_true', help='Explicitly permit installing lower version')
    args = parser.parse_args(argv)
    dst = Path(args.destination).expanduser().resolve()
    old, incoming = preflight(dst, args.allow_downgrade)
    entries = sources()
    changes = [(p, p.relative_to(ROOT)) for p in entries]
    print(f'420VaultBot upgrade: {old or "unknown"} -> {incoming} | {len(changes)} source files')
    print('USER DATA EXCLUDED: .env, databases, data/, logs/, .venv/, secrets and credentials')
    if args.dry_run:
        print('DRY RUN — destination left untouched')
        for _, rel in changes: print('  ', rel)
        return 0
    stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = dst / 'backups' / ('source_pre_v640_' + stamp)
    backup.mkdir(parents=True, exist_ok=False)
    manifest = {'old_version': old, 'new_version': incoming, 'source_files': [str(rel) for _, rel in changes]}
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf8')
    try: replace_with_rollback(dst, changes, backup)
    except Exception as exc:
        print(f'FAILED; attempted automatic rollback. Existing backup: {backup}. Error: {exc}', file=sys.stderr)
        return 1
    print(f'Upgrade complete. Previous overwritten code backed up to: {backup}')
    print('Restart the original bot instance. Check 420_version, 420_help and 420_admin.')
    return 0

if __name__ == '__main__':
    try: sys.exit(main())
    except (ValueError, OSError) as exc: print(f'Upgrade blocked: {exc}', file=sys.stderr); sys.exit(1)
