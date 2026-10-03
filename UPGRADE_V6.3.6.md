# 420VaultBot v6.3.6 — recovery release

Base: uploaded v6.2.4 source. Preserves its `420_help` button directory, command-center panel, admin and user views, user profiles, public-profile searching, authenticator 2FA, licensed/subscription features, and current service modules. Restores the account-welcome DM from v6.1.11 after verified email. Version identifiers and button-panel labels updated to v6.3.6.

## Upgrade an existing installation

1. Stop all running bot processes and take a complete offline backup of the installed bot directory, especially `.env`, all SQLite databases (`*.db`, `*.sqlite*`, including -wal/-shm), `data/`, `legacy/data/`, credentials, Google Drive tokens, link lists, licenses, and user accounts. Do not send secrets to anyone.
2. Extract this archive to a separate new directory. Do not overwrite an existing production folder wholesale.
3. Run `upgrade_existing.bat` from this extracted folder and point it at the existing production bot directory; the upgrader copies source only and refuses to overwrite live data, `.env` or `.venv`. It will create a dated source backup and stop on file-copy failures.
4. Ensure only this installation's entry point runs; stop an old background bot/watchdog/hosting copy if necessary. Keep existing Python environment, or install `requirements.txt` into an appropriately provisioned environment.
5. Start the normal bot launcher and use `420_version` and `420_help` in an allowed channel. Expect `v6.3.6` and paginated clickable buttons. The Command Center should be restored on startup in approved channels when the bot has Send Messages, Embed Links, Read Message History and Manage Messages / pin permissions as applicable.
6. Verify `#login` panel / authenticator 2FA, public profile search, admin tools, and the post-email-verification welcome DM on a test account before redeploying widely.

This is a source-reviewed merge and static-checked package, not a live Discord integration test. Features depend on production configuration and service credentials. The old v6.1.11 file mistakenly declares v6.1.10 in app/version.py; this package does not use that code as its base. No live user data from either uploaded snapshot has been bundled. Keep the production data intact.
