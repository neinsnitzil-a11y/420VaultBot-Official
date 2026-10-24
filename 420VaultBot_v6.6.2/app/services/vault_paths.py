"""Resolve indexed Vault records against one or more configured storage roots."""
from pathlib import Path

def _roots(root_or_roots):
    if not root_or_roots:return []
    if isinstance(root_or_roots,(str,Path)):return [str(root_or_roots)]
    out=[]
    for r in root_or_roots:
        if isinstance(r,dict):r=r.get("path")
        if r and str(r) not in out:out.append(str(r))
    return out

def resolve_vault_item(root_or_roots, record, kind="file"):
    roots=_roots(root_or_roots)
    preferred=str(record["source_root"] or "") if "source_root" in record.keys() else ""
    if preferred:roots=[preferred]+[r for r in roots if r!=preferred]
    if not roots:return None,"Vault roots are not configured",False
    expected_dir=kind=="folder"
    original=Path(record["full_path"]).expanduser()
    for root in roots:
        try:base=Path(root).expanduser().resolve()
        except Exception:continue
        if not base.is_dir():continue
        def safe(raw):
            try:path=Path(raw).expanduser().resolve()
            except Exception:return None
            if path!=base and base not in path.parents:return None
            if not (path.is_dir() if expected_dir else path.is_file()):return None
            return path
        found=safe(original)
        if found:return found,None,False
        if kind=="folder":
            try:relative=original.resolve().relative_to(Path(preferred).resolve()) if preferred else None
            except Exception:relative=None
            if relative is None:
                key=str(record["relative_path"] or "")
                parts=key.split("/",1);relative=Path(parts[1] if len(parts)>1 else ".")
        else:
            relative=Path(str(record["folder"] or ""))/str(record["filename"])
        found=safe(base/relative)
        if found:return found,None,True
    return None,"Indexed path is unavailable under all configured Vault roots",False

def repair_vault_path(db,guild_id,record,kind,path):
    table="vault_folders" if kind=="folder" else "vault_files"
    roots=db.vault_roots(guild_id,True) if hasattr(db,"vault_roots") else []
    source=""
    rp=Path(path).resolve()
    for r in roots:
        try:
            base=Path(r["path"]).resolve()
            if rp==base or base in rp.parents:source=str(base);break
        except Exception:pass
    try:db.execute(f"UPDATE {table} SET full_path=?,available=1,source_root=? WHERE guild_id=? AND id=?",(str(path),source,guild_id,record["id"]))
    except __import__("sqlite3").IntegrityError:pass
