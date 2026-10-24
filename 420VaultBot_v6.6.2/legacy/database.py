# project_structure/database.py
import sqlite3
import logging
from typing import List, Dict, Any, Optional
import os

log = logging.getLogger("VaultWhisperer_DB")

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize_db()
        log.info(f"DatabaseManager initialized for '{self.db_path}'")

    def _initialize_db(self):
        """Ensures the database and schema are correctly established."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # =========================
            # CORE VAULT FILES TABLE
            # =========================
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vault_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    full_path TEXT NOT NULL UNIQUE,
                    folder TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    modified_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT UNIQUE
                )
            ''')

            # Indexes for search performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_filename ON vault_files (filename COLLATE NOCASE)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_folder ON vault_files (folder COLLATE NOCASE)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extension ON vault_files (extension)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checksum ON vault_files (checksum)")

            # =========================
            # ANALYTICS TABLES
            # =========================
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS asset_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    user_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id TEXT PRIMARY KEY,
                    searches INTEGER DEFAULT 0,
                    downloads INTEGER DEFAULT 0
                )
            """)

            # =========================
            # DEAD LINK TRACKING (SAFE MIGRATION)
            # =========================
            try:
                cursor.execute("ALTER TABLE vault_files ADD COLUMN is_dead INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE vault_files ADD COLUMN last_checked DATETIME")
            except sqlite3.OperationalError:
                pass

            conn.commit()

        log.info("Database schema, analytics tables, and migrations verified.")

    # =====================================================
    # INTERNAL QUERY HELPER
    # =====================================================
    def _execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            log.error(f"Database error during query: {query} | params={params} | error={e}")
            return []

    # =====================================================
    # EXISTING VAULT METHODS (UNCHANGED)
    # =====================================================
    def get_file_by_id(self, file_id: int) -> Optional[Dict[str, Any]]:
        sql_query = "SELECT id, filename, full_path, folder, extension, file_size FROM vault_files WHERE id = ?"
        results = self._execute_query(sql_query, (file_id,))
        return results[0] if results else None

    def search_files(self, query_string: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not query_string:
            return []

        keywords = query_string.split()
        conditions = []
        params = []

        for keyword in keywords:
            conditions.append("(filename COLLATE NOCASE LIKE ? OR folder COLLATE NOCASE LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        where_clause = " AND ".join(conditions)
        sql_query = f"""
            SELECT id, filename, folder, extension, file_size
            FROM vault_files
            WHERE {where_clause}
            ORDER BY filename COLLATE NOCASE
            LIMIT ?
        """
        params.append(limit)
        return self._execute_query(sql_query, tuple(params))

    def get_random_file(self) -> Optional[Dict[str, Any]]:
        sql_query = """
            SELECT id, filename, full_path, folder, extension, file_size
            FROM vault_files
            ORDER BY RANDOM()
            LIMIT 1
        """
        results = self._execute_query(sql_query)
        return results[0] if results else None

    def get_stats(self) -> Dict[str, Any]:
        total_files = self._execute_query("SELECT COUNT(*) FROM vault_files")[0]['COUNT(*)']
        total_size = self._execute_query("SELECT SUM(file_size) FROM vault_files")[0]['SUM(file_size)'] or 0
        last_modified = self._execute_query("SELECT MAX(modified_at) FROM vault_files")[0]['MAX(modified_at)']

        return {
            "total_indexed_files": total_files,
            "total_storage_size_bytes": total_size,
            "last_scan_time": last_modified
        }

    def get_all_files(self, limit: int = 20) -> List[Dict[str, Any]]:
        sql_query = """
            SELECT id, filename, folder, extension, file_size
            FROM vault_files
            ORDER BY folder, filename
            LIMIT ?
        """
        return self._execute_query(sql_query, (limit,))

    def get_folder_contents(self, folder_path: str, limit: int = 20) -> List[Dict[str, Any]]:
        sql_query = """
            SELECT id, filename, folder, extension, file_size
            FROM vault_files
            WHERE folder COLLATE NOCASE LIKE ?
            ORDER BY filename COLLATE NOCASE
            LIMIT ?
        """
        return self._execute_query(sql_query, (f"{folder_path}%", limit))

    def get_unique_folders(self, parent_folder: str = '', limit: int = 20) -> List[str]:
        search_path = os.path.join(parent_folder, '')
        sql_query = """
            SELECT DISTINCT folder
            FROM vault_files
            WHERE folder LIKE ?
            ORDER BY folder COLLATE NOCASE
            LIMIT ?
        """
        rows = self._execute_query(sql_query, (f"{search_path}%", limit))
        full_folders = [row['folder'] for row in rows]

        unique = set()
        for fpath in full_folders:
            rel = os.path.relpath(fpath, parent_folder)
            if rel == ".":
                continue
            unique.add(os.path.join(parent_folder, rel.split(os.sep)[0]))

        return sorted(unique)

    # =====================================================
    # NEW: ANALYTICS & COMMUNITY METHODS
    # =====================================================
    def log_asset_event(self, asset_name: str, event_type: str, user_id: Optional[str] = None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO asset_events (asset_name, event_type, user_id)
                VALUES (?, ?, ?)
            """, (asset_name, event_type, user_id))
            conn.commit()

    def update_user_stats(self, user_id: str, action: str):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO user_stats (user_id, searches, downloads)
                VALUES (?, 0, 0)
                ON CONFLICT(user_id) DO NOTHING
            """, (user_id,))

            if action == "search":
                cursor.execute(
                    "UPDATE user_stats SET searches = searches + 1 WHERE user_id = ?",
                    (user_id,)
                )
            elif action == "download":
                cursor.execute(
                    "UPDATE user_stats SET downloads = downloads + 1 WHERE user_id = ?",
                    (user_id,)
                )

            conn.commit()

    def get_trending_assets(self, hours: int = 24, limit: int = 10) -> List[Dict[str, Any]]:
        sql_query = """
            SELECT asset_name, COUNT(*) as hits
            FROM asset_events
            WHERE timestamp >= datetime('now', ?)
            GROUP BY asset_name
            ORDER BY hits DESC
            LIMIT ?
        """
        return self._execute_query(sql_query, (f"-{hours} hours", limit))

    # =====================================================
    # NEW: DEAD LINK MANAGEMENT
    # =====================================================
    def mark_link_dead(self, file_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE vault_files
                SET is_dead = 1,
                    last_checked = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (file_id,))
            conn.commit()

    def mark_link_alive(self, file_id: int):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE vault_files
                SET is_dead = 0,
                    last_checked = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (file_id,))
            conn.commit()
