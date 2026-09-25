# project_structure/indexer.py
import os
import sqlite3
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("VaultWhisperer_Indexer")

# --- Paths ---
VAULT_PATH = "/mnt/e/420 VAULT"
DATABASE_PATH = "./data/vault_files.db"
os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

# --- Config ---
VALID_EXTENSIONS = {
    "wav", "mp3", "flac", "aiff", "aif",
    "flp", "mid", "midi", "ogg"
}

IGNORED_FILES = {
    ".ds_store", "thumbs.db", "desktop.ini", "._.ds_store"
}

IGNORED_FOLDERS = {
    "__macosx"
}

# --- Retry Config ---
MAX_RETRIES = 5
RETRY_DELAY = 2  # seconds


def safe_commit(conn):
    retries = 0
    while retries < MAX_RETRIES:
        try:
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                retries += 1
                log.warning(f"Database locked. Retrying {retries}/{MAX_RETRIES} in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
            else:
                raise
    log.error("Failed to commit after multiple retries. Skipping this batch.")
    return False


class Indexer:
    def __init__(self, vault_path: str, db_path: str):
        self.vault_path = os.path.abspath(vault_path)
        self.db_path = db_path
        self._init_db()

        if not os.path.isdir(self.vault_path):
            raise FileNotFoundError(self.vault_path)

        log.info(f"Indexer ready | Vault: {self.vault_path}")

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vault_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    full_path TEXT NOT NULL UNIQUE,
                    folder TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    modified_at TEXT NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_filename ON vault_files (filename COLLATE NOCASE)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_folder ON vault_files (folder COLLATE NOCASE)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_extension ON vault_files (extension)")
            safe_commit(conn)

    def _get_metadata(self, path: str):
        try:
            if not os.path.isfile(path):
                return None

            name = os.path.basename(path)
            if name.startswith(".") or name.lower() in IGNORED_FILES:
                return None

            folder = os.path.dirname(path)
            if any(p.lower() in IGNORED_FOLDERS for p in folder.split(os.sep)):
                return None

            ext = os.path.splitext(name)[1].lower().lstrip(".")
            if ext not in VALID_EXTENSIONS:
                return None

            stat = os.stat(path)

            return {
                "filename": name,
                "full_path": path,
                "folder": folder,
                "extension": ext,
                "file_size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }

        except Exception as e:
            log.warning(f"Metadata error: {path} ({e})")
            return None

    def _execute_with_retry(self, conn, sql, params=()):
        """Retry inserts/updates if database is locked."""
        retries = 0
        while retries < MAX_RETRIES:
            try:
                cur = conn.cursor()
                cur.execute(sql, params)
                safe_commit(conn)
                return True
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    retries += 1
                    log.warning(f"Database locked during query. Retrying {retries}/{MAX_RETRIES} in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
                else:
                    raise
        log.error(f"Failed to execute SQL after {MAX_RETRIES} retries: {sql} | Params: {params}")
        return False

    def scan_and_index(self, incremental=True):
        log.info("Starting vault scan (FAST MODE, incremental-safe)...")
        start = time.time()

        processed = added = updated = removed = 0
        BATCH_SIZE = 500

        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        cur = conn.cursor()

        try:
            for root, dirs, files in os.walk(self.vault_path):
                dirs[:] = [d for d in dirs if d.lower() not in IGNORED_FOLDERS]

                for file in files:
                    full_path = os.path.join(root, file)
                    meta = self._get_metadata(full_path)
                    if not meta:
                        continue

                    processed += 1

                    cur.execute(
                        "SELECT id, modified_at FROM vault_files WHERE full_path=?",
                        (full_path,)
                    )
                    record = cur.fetchone()

                    if record:
                        db_id, db_mod = record
                        if incremental and meta["modified_at"] <= db_mod:
                            continue

                        cur.execute("""
                            UPDATE vault_files SET
                                filename=?, folder=?, extension=?,
                                file_size=?, modified_at=?
                            WHERE id=?
                        """, (
                            meta["filename"],
                            meta["folder"],
                            meta["extension"],
                            meta["file_size"],
                            meta["modified_at"],
                            db_id
                        ))
                        updated += 1
                    else:
                        cur.execute("""
                            INSERT OR IGNORE INTO vault_files
                            (filename, full_path, folder, extension, file_size, created_at, modified_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            meta["filename"],
                            meta["full_path"],
                            meta["folder"],
                            meta["extension"],
                            meta["file_size"],
                            meta["created_at"],
                            meta["modified_at"]
                        ))
                        added += 1

                    if processed % BATCH_SIZE == 0:
                        conn.commit()
                        log.info(
                            f"Processed: {processed} | Added: {added} | Updated: {updated}"
                        )

            conn.commit()

        except sqlite3.OperationalError as e:
            log.error(f"SQLite error: {e}")

        finally:
            conn.close()

        log.info(
            f"SCAN COMPLETE | "
            f"Processed: {processed} | Added: {added} | Updated: {updated} | "
            f"Time: {time.time() - start:.2f}s"
        )

        # Load existing DB records
        existing = {}
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id, full_path, modified_at FROM vault_files")
            for row in cur.fetchall():
                existing[row[1]] = row

        found = set()
        processed = added = updated = removed = 0

        for root, dirs, files in os.walk(self.vault_path):
            dirs[:] = [d for d in dirs if d.lower() not in IGNORED_FOLDERS]

            for file in files:
                full_path = os.path.join(root, file)
                found.add(full_path)

                meta = self._get_metadata(full_path)
                if not meta:
                    continue

                record = existing.get(full_path)

                # Incremental skip
                if incremental and record and meta["modified_at"] <= record[2]:
                    continue  # Already indexed and not modified

                processed += 1
                if processed % 500 == 0:
                    log.info(f"Processed: {processed} | Added: {added} | Updated: {updated}")

                with sqlite3.connect(self.db_path) as conn:
                    if record:
                        db_id, _, db_mod = record
                        if meta["modified_at"] > db_mod:
                            sql = """
                                UPDATE vault_files SET
                                    filename=?, folder=?, extension=?,
                                    file_size=?, modified_at=?
                                WHERE id=?
                            """
                            params = (
                                meta["filename"], meta["folder"],
                                meta["extension"], meta["file_size"],
                                meta["modified_at"], db_id
                            )
                            if self._execute_with_retry(conn, sql, params):
                                updated += 1
                    else:
                        sql = """
                            INSERT INTO vault_files
                            (filename, full_path, folder, extension, file_size, created_at, modified_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """
                        params = (
                            meta["filename"], meta["full_path"],
                            meta["folder"], meta["extension"],
                            meta["file_size"], meta["created_at"],
                            meta["modified_at"]
                        )
                        if self._execute_with_retry(conn, sql, params):
                            added += 1

        # Only delete stale files if not incremental
        if not incremental:
            stale = set(existing.keys()) - found
            with sqlite3.connect(self.db_path) as conn:
                for path in stale:
                    sql = "DELETE FROM vault_files WHERE full_path=?"
                    if self._execute_with_retry(conn, sql, (path,)):
                        removed += 1

        log.info(
            f"SCAN COMPLETE | "
            f"Processed: {processed} | Added: {added} | "
            f"Updated: {updated} | Removed: {removed} | "
            f"Time: {time.time() - start:.2f}s"
        )


if __name__ == "__main__":
    load_dotenv()
    # Default full scan
    Indexer(VAULT_PATH, DATABASE_PATH).scan_and_index(incremental=True)
