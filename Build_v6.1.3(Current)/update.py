#!/usr/bin/env python3
"""
420VaultBot Universal Manual Updater

Update contract (v6.2.2+):
- Code is updated in place.
- Persistent/runtime state is NEVER replaced by release payloads.
- A verified backup of persistent state is created before code installation.
- Virtual environments are preserved in place (not copied into backups because they
  can be recreated from requirements.txt and may be very large).
- Existing accounts, sessions, 2FA state, profiles, licenses, subscriptions and
  guild configuration remain in data/420vault.db.

Run this file FROM the existing bot installation you want to update.
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, shutil, sqlite3, tempfile, zipfile
from pathlib import Path

# Directories/files that are user-owned runtime state. Release ZIPs are forbidden
# from overwriting these paths.
PRESERVE_IN_PLACE = {
    ".env", ".venv", "venv",
    "data", "config", "linklists", "backups", "logs",
    "credentials", "google_drive", "vault_index", "preview_cache",
    "tools", "vault", "downloads", "exports"
}
# Everything above except rebuildable/large virtual environments is backed up.
BACKUP_PATHS = PRESERVE_IN_PLACE - {".venv", "venv", "backups"}
UPDATER_FILES = {"update.py", "update.bat"}
STATE = Path("data/install_state.json")
CRITICAL_TABLES = (
    "auth_accounts", "auth_sessions", "user_profiles", "licenses",
    "subscriptions", "subscription_plans", "guild_settings", "tos_acceptances"
)

def load_json(p, default=None):
    try:return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception:return default

def save_json(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(value,indent=2),encoding="utf-8")
    os.replace(t,p)

def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def is_protected(rel):
    s=rel.as_posix().strip("/").lower()
    return any(s==x.lower() or s.startswith(x.lower()+"/") for x in PRESERVE_IN_PLACE)

def safe_extract(zf,dest):
    base=dest.resolve()
    for info in zf.infolist():
        target=(dest/info.filename).resolve()
        if target!=base and base not in target.parents:raise RuntimeError(f"Unsafe ZIP member: {info.filename}")
    zf.extractall(dest)

def sqlite_ok(p):
    try:
        with sqlite3.connect(p) as c:return c.execute("PRAGMA integrity_check").fetchone()[0].lower()=="ok"
    except Exception:return False

def critical_snapshot(install):
    """Snapshot critical auth/license/account state for a post-copy preservation check."""
    out={"env":None,"db":None,"twofa_key":None,"venv_exists":False,"venv_python":False}
    env=install/".env"
    if env.is_file():out["env"]=sha256(env)
    key=install/"data"/"auth_2fa_secret.key"
    if key.is_file():out["twofa_key"]=sha256(key)
    out["venv_exists"]=(install/".venv").exists() or (install/"venv").exists()
    out["venv_python"]=(install/".venv"/"Scripts"/"python.exe").is_file() or (install/"venv"/"Scripts"/"python.exe").is_file()
    db=install/"data"/"420vault.db"
    if db.is_file():
        if not sqlite_ok(db):raise RuntimeError("Existing data/420vault.db failed SQLite integrity_check before update.")
        counts={}
        with sqlite3.connect(db) as c:
            names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in CRITICAL_TABLES:
                if table in names:counts[table]=int(c.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        out["db"]={"sha256":sha256(db),"counts":counts}
    return out

def backup(install):
    b=install/"backups"/("update_"+dt.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    b.mkdir(parents=True,exist_ok=False);copied=[];files=[];dbchecks={}
    for name in sorted(BACKUP_PATHS):
        src=install/name
        if not src.exists():continue
        dst=b/name;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(src,dst,copy_function=shutil.copy2) if src.is_dir() else shutil.copy2(src,dst)
        copied.append(name)
    for f in b.rglob("*"):
        if f.is_file():
            files.append({"path":str(f.relative_to(b)),"sha256":sha256(f),"size":f.stat().st_size})
            if f.suffix.lower()==".db":dbchecks[str(f.relative_to(b))]=sqlite_ok(f)
    if any(v is False for v in dbchecks.values()):
        shutil.rmtree(b,ignore_errors=True);raise RuntimeError("Persistent-data backup failed SQLite integrity verification.")
    save_json(b/"backup_manifest.json",{
        "version":2,"created_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "protected":copied,"preserved_in_place":sorted(PRESERVE_IN_PLACE),
        "files":files,"sqlite_integrity":dbchecks
    })
    return b

def verify_backup(b):
    m=load_json(b/"backup_manifest.json",{}) or {}
    for row in m.get("files",[]):
        p=b/row["path"]
        if not p.is_file() or sha256(p)!=row["sha256"]:raise RuntimeError("Backup verification failed: "+row["path"])
    for rel,ok in m.get("sqlite_integrity",{}).items():
        if not ok or not sqlite_ok(b/rel):raise RuntimeError("Backup SQLite verification failed: "+rel)

def restore(install,b):
    verify_backup(b);m=load_json(b/"backup_manifest.json",{}) or {}
    for name in m.get("protected",[]):
        src,dst=b/name,install/name
        if not src.exists():continue
        if dst.exists():shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(src,dst,copy_function=shutil.copy2) if src.is_dir() else shutil.copy2(src,dst)

def resolve_source(raw,temp):
    p=Path(raw).expanduser().resolve()
    if p.is_dir():print("[SOURCE] Extracted folder:",p);return p
    if p.is_file() and zipfile.is_zipfile(p):
        d=temp/"extracted_release";d.mkdir()
        with zipfile.ZipFile(p) as z:safe_extract(z,d)
        print("[SOURCE] ZIP:",p);return d
    if p.is_file():raise RuntimeError("Selected file is not a valid ZIP.")
    raise RuntimeError("Selected update path does not exist.")

def unwrap_single_folder(src):
    cur=src
    for _ in range(4):
        entries=[x for x in cur.iterdir() if x.name!="__MACOSX"];dirs=[x for x in entries if x.is_dir()];files=[x for x in entries if x.is_file()]
        if len(dirs)==1 and not files:cur=dirs[0]
        else:break
    return cur

def detect_release(src):
    src=unwrap_single_folder(src)
    if (src/"update_manifest.json").is_file() and (src/"payload").is_dir():return "manifest",src/"payload",src
    markers=["requirements.txt","requirements.lock","pyproject.toml","VERSION",".env.example","start.bat","run.bat","install.bat"]
    if list(src.glob("*.py")) or any((src/x).is_dir() for x in ("app","bot","src","cogs")) or any((src/x).exists() for x in markers):return "full",src,src
    candidates=[]
    for d in [x for x in src.iterdir() if x.is_dir()]:
        score=len(list(d.glob("*.py")))+sum((d/x).exists() for x in markers)+sum((d/x).is_dir() for x in ("app","bot","src","cogs"))
        if score:candidates.append((score,d))
    if candidates:candidates.sort(reverse=True,key=lambda x:x[0]);return "full",candidates[0][1],candidates[0][1]
    raise RuntimeError("Could not recognize this as a 420VaultBot build. Select the bot folder or full-build ZIP.")

def copy_release(payload,install):
    count=skipped=0
    for src in payload.rglob("*"):
        if src.is_dir():continue
        rel=src.relative_to(payload)
        if is_protected(rel):print("[PRESERVE]",rel);skipped+=1;continue
        if "__pycache__" in rel.parts or rel.suffix==".pyc":skipped+=1;continue
        if rel.as_posix().lower() in UPDATER_FILES:print("[KEEP CURRENT UPDATER]",rel);skipped+=1;continue
        dst=install/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);count+=1
    return count,skipped

def release_version(payload):
    vf=payload/"VERSION"
    if vf.is_file():return vf.read_text(encoding="utf-8").strip()
    vp=payload/"app"/"version.py"
    if vp.is_file():
        import re
        m=re.search(r"VERSION\s*=\s*['\"]([^'\"]+)",vp.read_text(encoding="utf-8",errors="ignore"))
        if m:return m.group(1)
    return ""

def run_legacy_migrations(install,release_root,manifest):
    state=load_json(install/STATE,{"completed_migrations":[]}) or {};done=set(state.get("completed_migrations",[]))
    for m in manifest.get("migrations",[]):
        mid=str(m["id"])
        if mid in done:continue
        db=install/m["database"];sql=release_root/m["sql"];db.parent.mkdir(parents=True,exist_ok=True);con=sqlite3.connect(db)
        try:con.executescript(sql.read_text(encoding="utf-8"));con.commit()
        except Exception:con.rollback();raise
        finally:con.close()
        done.add(mid)
    state["completed_migrations"]=sorted(done)
    if manifest.get("version"):state["installed_version"]=manifest["version"]
    save_json(install/STATE,state)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("source",help="New full-build ZIP OR extracted folder");ap.add_argument("--install-dir",default=".",help="Existing bot installation to update");args=ap.parse_args()
    install=Path(args.install_dir).resolve()
    print("="*60);print("420VaultBot Universal Manual Updater v6.2.2+");print("INSTALLATION:",install);print("="*60)
    with tempfile.TemporaryDirectory(prefix="420vault_update_") as td:
        src=resolve_source(args.source,Path(td));kind,payload,release_root=detect_release(src)
        if payload.resolve()==install.resolve():raise RuntimeError("Update SOURCE is the same folder as CURRENT INSTALLATION. Select the NEW release ZIP/folder.")
        print("[TYPE]", "Extracted/full build" if kind=="full" else "Manifest release");print("[BOT ROOT]",payload);print("[RELEASE VERSION]",release_version(payload) or "unknown")
        before=critical_snapshot(install)
        print("\nCreating and verifying persistent-data backup...");b=backup(install);verify_backup(b);print("[BACKUP]",b)
        try:
            count,skipped=copy_release(payload,install)
            if kind=="manifest":run_legacy_migrations(install,release_root,load_json(release_root/"update_manifest.json",{}) or {})
            after=critical_snapshot(install)
            # DB file hash must remain identical during code copy. Migrations, when explicitly
            # declared in manifest releases, are allowed to alter DB schema/data.
            check_before=dict(before);check_after=dict(after)
            if kind=="manifest":
                if check_before.get("db") and check_after.get("db"):
                    check_before["db"]={"counts":check_before["db"].get("counts",{})}
                    check_after["db"]={"counts":check_after["db"].get("counts",{})}
            if check_before!=check_after:raise RuntimeError("Preservation verification failed: critical account/license/config/2FA/.venv state changed during update.")
            state=load_json(install/STATE,{}) or {};rv=release_version(payload) or (load_json(release_root/"update_manifest.json",{}) or {}).get("version","")
            if rv:state["installed_version"]=rv
            state["last_update"]=dt.datetime.now(dt.timezone.utc).isoformat();state["last_backup"]=str(b);state["preservation_policy_version"]=2;save_json(install/STATE,state)
            print("\n"+"="*60);print("UPDATE SUCCESSFUL");print("Files updated:",count);print("Protected/skipped:",skipped);print("Accounts/logins/licenses/profiles/2FA/.env/.venv preserved.");print("Backup:",b);print("="*60)
        except Exception:
            print("\nUPDATE FAILED - restoring persistent data...");restore(install,b);print("Persistent data restored. .venv was never touched.");raise
if __name__=="__main__":main()
