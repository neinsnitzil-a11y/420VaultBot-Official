# v6.4.2 physical Vault reconnect / download repair

Fixes: unchanged files regain `available=1` when seen during a scan; physical Vault preview, browsing and legacy/unified delivery resolve paths against the *current* configured root if an indexed absolute path is stale; relocated paths are accepted only within that configured root; `.DS_Store` and similar metadata are excluded from new indexing and search results; unavailable items are filtered from search.

The fallback requires the file's relative folder and filename to be unchanged. It cannot restore deleted files or access a disconnected drive, nor does it bypass Discord upload limits. If search panels reference old IDs, launch a new search after **Scan Changes**. If a file is still unavailable, verify that the bot host sees its current storage path.

## Upgrade safely

1. Stop the bot. Back up the complete existing installation, including `.env`, account and license databases, Drive credentials, custom config and Vault index.
2. Extract this ZIP **to a new directory** (do not extract it over a live installation).
3. Use the existing installation's trusted update/backup workflow to replace application code, leaving existing runtime `data/`, `.env`, `.venv`, and backups intact. Avoid blindly copying any old sample data into live folders.
4. Start the bot, confirm the configured Vault root, run **Scan Changes**, then launch a fresh search and test a known WAV file's preview and download.

No live Discord environment or physical E: drive was available for integration testing. Unit tests and Python compilation passed. The release excludes bundled user runtime data and Python virtual environment.
