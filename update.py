#!/usr/bin/env python3
"""
420VaultBot Universal Manual Updater
Accepts:
  1) a full-build ZIP
  2) an extracted full-build folder
  3) legacy manifest/payload releases

Run this file FROM the existing bot installation you want to update.
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, shutil, sqlite3, tempfile, zipfile
from pathlib import Path

PROTECTED = {
    ".env", "data", "config", "linklists", "backups", "logs",
    "credentials", "google_drive", "vault_index", "preview_cache"
}
UPDATER_FILES = {"update.py", "update.bat"}
STATE = Path("data/install_state.json")

def load_json(p, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default
    except Exception:
        return default

def save_json(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix(p.suffix + ".tmp")
    t.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(t, p)

def is_protected(rel):
    s = rel.as_posix().strip("/").lower()
    return any(s == x.lower() or s.startswith(x.lower() + "/") for x in PROTECTED)

def safe_extract(zf, dest):
    base = dest.resolve()
    for info in zf.infolist():
        target = (dest / info.filename).resolve()
        if target != base and base not in target.parents:
            raise RuntimeError(f"Unsafe ZIP member: {info.filename}")
    zf.extractall(dest)

def backup(install):
    b = install / "backups" / ("update_" + dt.datetime.now().strftime("%Y-%m-%d_%H%M%S"))
    b.mkdir(parents=True, exist_ok=False)
    copied = []
    for name in sorted(PROTECTED):
        if name == "backups":
            continue
        src = install / name
        if not src.exists():
            continue
        dst = b / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, copy_function=shutil.copy2)
        else:
            shutil.copy2(src, dst)
        copied.append(name)
    save_json(b / "backup_manifest.json", {"protected": copied})
    return b

def restore(install, b):
    m = load_json(b / "backup_manifest.json", {}) or {}
    for name in m.get("protected", []):
        src, dst = b / name, install / name
        if not src.exists():
            continue
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, copy_function=shutil.copy2) if src.is_dir() else shutil.copy2(src, dst)

def resolve_source(raw, temp):
    p = Path(raw).expanduser().resolve()
    if p.is_dir():
        print("[SOURCE] Extracted folder:", p)
        return p
    if p.is_file() and zipfile.is_zipfile(p):
        d = temp / "extracted_release"
        d.mkdir()
        with zipfile.ZipFile(p) as z:
            safe_extract(z, d)
        print("[SOURCE] ZIP:", p)
        return d
    if p.is_file():
        raise RuntimeError("Selected file is not a valid ZIP.")
    raise RuntimeError("Selected update path does not exist.")

def unwrap_single_folder(src):
    # ZIPs commonly contain one top-level folder. Walk through harmless wrappers.
    cur = src
    for _ in range(4):
        entries = [x for x in cur.iterdir() if x.name not in {"__MACOSX"}]
        dirs = [x for x in entries if x.is_dir()]
        files = [x for x in entries if x.is_file()]
        if len(dirs) == 1 and not files:
            cur = dirs[0]
        else:
            break
    return cur

def detect_release(src):
    src = unwrap_single_folder(src)

    # Legacy packaged updater format.
    if (src / "update_manifest.json").is_file() and (src / "payload").is_dir():
        return "manifest", src / "payload", src

    # Normal full bot build. Detect common project markers rather than requiring manifest.
    markers = [
        "requirements.txt", "requirements.lock", "pyproject.toml",
        "VERSION", ".env.example", "start.bat", "run.bat", "install.bat"
    ]
    python_files = list(src.glob("*.py"))
    subdirs = [src / x for x in ("app", "bot", "src", "cogs") if (src / x).is_dir()]
    if python_files or subdirs or any((src / x).exists() for x in markers):
        return "full", src, src

    # Search one level down for an actual bot root if the selected folder was a parent folder.
    candidates = []
    for d in [x for x in src.iterdir() if x.is_dir()]:
        score = len(list(d.glob("*.py"))) + sum((d / x).exists() for x in markers)
        score += sum((d / x).is_dir() for x in ("app","bot","src","cogs"))
        if score:
            candidates.append((score, d))
    if candidates:
        candidates.sort(reverse=True, key=lambda x: x[0])
        return "full", candidates[0][1], candidates[0][1]

    raise RuntimeError(
        "Could not recognize this as a 420VaultBot build. "
        "Select the extracted bot folder itself, or the full-build ZIP."
    )

def copy_release(payload, install):
    count = 0
    skipped = 0
    for src in payload.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(payload)
        if is_protected(rel):
            print("[PRESERVE]", rel)
            skipped += 1
            continue
        # Don't replace the currently executing updater during its own run.
        if rel.as_posix().lower() in UPDATER_FILES:
            print("[KEEP CURRENT UPDATER]", rel)
            skipped += 1
            continue
        dst = install / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        count += 1
    return count, skipped

def run_legacy_migrations(install, release_root, manifest):
    state = load_json(install / STATE, {"completed_migrations": []}) or {}
    done = set(state.get("completed_migrations", []))
    for m in manifest.get("migrations", []):
        mid = str(m["id"])
        if mid in done:
            continue
        db = install / m["database"]
        sql = release_root / m["sql"]
        db.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(db)
        try:
            con.executescript(sql.read_text(encoding="utf-8"))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        done.add(mid)
    state["completed_migrations"] = sorted(done)
    if manifest.get("version"):
        state["installed_version"] = manifest["version"]
    save_json(install / STATE, state)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="New full-build ZIP OR extracted folder")
    ap.add_argument("--install-dir", default=".", help="Existing bot installation to update")
    args = ap.parse_args()

    install = Path(args.install_dir).resolve()
    print("============================================================")
    print("420VaultBot Universal Manual Updater")
    print("INSTALLATION:", install)
    print("============================================================")

    with tempfile.TemporaryDirectory(prefix="420vault_update_") as td:
        src = resolve_source(args.source, Path(td))
        kind, payload, release_root = detect_release(src)

        # Guard against selecting the same installation as the source.
        try:
            if payload.resolve() == install.resolve():
                raise RuntimeError(
                    "The update SOURCE is the same folder as the CURRENT INSTALLATION. "
                    "Select the NEW version folder/ZIP instead."
                )
        except FileNotFoundError:
            pass

        print("[TYPE]", "Extracted/full build" if kind == "full" else "Manifest release")
        print("[BOT ROOT]", payload)

        print("\nCreating persistent-data backup...")
        b = backup(install)
        print("[BACKUP]", b)

        try:
            count, skipped = copy_release(payload, install)
            if kind == "manifest":
                manifest = load_json(release_root / "update_manifest.json", {}) or {}
                run_legacy_migrations(install, release_root, manifest)
            else:
                # Best-effort version recording for normal builds.
                state = load_json(install / STATE, {}) or {}
                version_file = payload / "VERSION"
                if version_file.exists():
                    state["installed_version"] = version_file.read_text(encoding="utf-8").strip()
                state["last_update"] = dt.datetime.now().isoformat()
                state["last_backup"] = str(b)
                save_json(install / STATE, state)

            print("\n============================================================")
            print("UPDATE SUCCESSFUL")
            print("Files updated:", count)
            print("Protected/skipped:", skipped)
            print("Persistent data preserved.")
            print("============================================================")
        except Exception:
            print("\nUPDATE FAILED - restoring persistent data...")
            restore(install, b)
            print("Persistent data restored.")
            raise

if __name__ == "__main__":
    main()
