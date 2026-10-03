# 420VaultBot v6.4.1 — Source audit and reliability patch

## Scope and limits
Reviewed the supplied v6.4.0 archive (89 Python files), traced Discord backup callbacks, in-app updater, database backups, version displays, and performed a static syntax pass across app/. Ran focused offline regression tests. No Discord token, real user database, payment provider, Google Drive credentials, or live server environment was available. This is **not** a certification that every command or integration works; the findings below identify confirmed defects and open risks.

## Fixed and verified offline
1. **Backup Now interaction timeout.** In `app/views/admin.py`, the old `update_backup` callback made `create_backup` finish before replying. Discord interactions require prompt acknowledgement, explaining why backups appeared on disk while the red failure banner appeared. Now defers immediately, performs work off-thread, and uses a follow-up response with success or failure.
2. **Inconsistent live SQLite file copies.** The old updater used ordinary directory copies for databases in WAL mode. Live copies can miss uncheckpointed changes; this patch uses SQLite's native backup API for `.db`, `.sqlite`, and `.sqlite3` files, and excludes journal sidecars in snapshots. Tested against a live WAL connection.
3. **Backup name collisions.** Previously names had one-second resolution, so simultaneous manual/daily backups could collide. Names now include microseconds and a random suffix.
4. **False success when backup incomplete.** Backup creation now performs checksum + SQLite integrity verification before returning success.
5. **Restore manifest validation.** Backups with out-of-root relative paths are rejected; restore targets are restricted to protected names.
6. **Incorrect version displays.** Admin footer was hardcoded to v6.1.4 and other command panels mentioned v6.3.6; all are now updated to v6.4.1 (admin footer uses the live VERSION constant).

## Important remaining risks (not fixed in this patch)
- **In-Discord update rollback isn't transactional for code files.** `app/services/updater.py:install_update` copies into the live source tree and `restore_backup` restores protected data only. For now prefer the stop-bot, command-line `upgrade_existing.bat` path that backs up overwritten source. A staged swap and verified program-code rollback need further design/test.
- **Disk pressure:** backup still copies entire protected directories (including `tools`), potentially large. Add backup size estimation, exclusions for reproducible caches, disk-space gates and configurable retention.
- **Remaining interactions:** more Discord button callbacks perform synchronous SQL or filesystem work before a response. An end-to-end interaction timing test harness is needed; do not assume all controls are fixed by this patch.
- **DB concurrency:** retry helper uses blocking `time.sleep` if a synchronous query hits SQLite busy state on the event-loop thread. Converting expensive read/write routes to thread-executed functions requires testing.
- **Silent exception handling:** 23 catch-and-pass patterns across the source warrant review for visibility and log hygiene.
- **Payments/auth/security:** no credentials/sandbox webhooks/live database were available, so renewal, event idempotency, access control, 2FA recovery and payment claims need behavioral tests; static presence of modules is insufficient.
- **Full suite:** the only full-suite import error in this environment was `ModuleNotFoundError: discord` (third-party dependencies are not installed here). Version-specific offline suite passed after updating expected release numbers.

## Installation caution
Stop the bot, back up the entire install yourself, and use `upgrade_existing.bat` from the extracted v6.4.1 source. Do not run multiple bot processes using the same installation. Verify `420_version`, press Backup Now, confirm its ephemeral success message and run Verify Latest; inspect `logs/` for errors. The red timeout on old Discord messages can persist; issue a fresh `420_admin` command to load updated buttons. Do not ship live `.env` or runtime data with the commercial archive.
