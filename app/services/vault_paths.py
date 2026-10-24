"""Resolve indexed Vault records against the current configured storage root."""
from pathlib import Path

def resolve_vault_item(root, record, kind="file"):
    """Return (path, reason, moved). Never return a path outside the configured root."""
    if not root:
        return None, "Vault root is not configured", False
    base = Path(root).expanduser().resolve()
    if not base.is_dir():
        return None, "Configured Vault root is offline or inaccessible", False
    expected_dir = kind == "folder"
    def safe_candidate(raw):
        path = Path(raw).expanduser().resolve()
        if path != base and base not in path.parents:
            return None
        if not (path.is_dir() if expected_dir else path.is_file()):
            return None
        return path
    original = Path(record["full_path"])
    found = safe_candidate(original)
    if found is not None:
        return found, None, False
    if kind == "folder":
        relative = str(record["relative_path"] or ".").replace("\\", "/")
    else:
        relative = str(record["folder"] or "").replace("\\", "/")
        relative = str(Path(relative) / str(record["filename"]))
    found = safe_candidate(base / relative)
    if found is not None:
        return found, None, True
    return None, "Indexed path is unavailable under the configured Vault root", False

def repair_vault_path(db, guild_id, record, kind, path):
    table = "vault_folders" if kind == "folder" else "vault_files"
    try:
        db.execute(f"UPDATE {table} SET full_path=?, available=1 WHERE guild_id=? AND id=?", (str(path), guild_id, record["id"]))
    except __import__("sqlite3").IntegrityError:
        # A newer scan may already own this absolute path; delivery can still proceed.
        pass
