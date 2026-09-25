# 420VaultBot v3.2

Integrated Vault storage, DM license activation, subscriptions and modular payments.

## Default plans
- $25 Monthly (30 days)
- $50 Half Year (182 days)
- $100 Yearly (365 days)
- $150 Lifetime (no automatic expiration)

Admins can change/add plans from `420_admin`. Lifetime licenses do not expire automatically, but administrators retain emergency/security revocation.

## Licensing
There is no `420_activatelicense` command. Generated subscription licenses are delivered by DM with an **Activate License** button. `420_resendlicense @user` resends it. Manual `420_addlicense @user 100` still means exactly 100 days.

## Vault
`420_admin` -> Vault Storage accepts any accessible local/external/network path. The drive does not need to be named 420Vault.

## Payments
Cash App is manual and administrator-verified. Stripe and PayPal use hosted/provider checkout and verified webhooks. Raw card/CVV data is intentionally never stored by this bot; provider vault tokens/IDs are used for renewals.

API secrets go in `.env`. Configure Stripe Price IDs / PayPal Plan IDs per plan in the Subscription Plans editor. Enable the local webhook service with `WEBHOOK_ENABLED=1`. It exposes `/webhooks/stripe`, `/webhooks/paypal`, and `/health` on the configured local host/port. Your public HTTPS reverse proxy/tunnel should forward to this listener.

## Windows install
Run `install.bat`. It bootstraps Python 3.12 with winget if necessary, creates the venv, upgrades pip, installs requirements, and launches the bot.

## v3.2 signed licenses + Base44 shared secret
On first setup, `setup_and_start.py` generates separate secrets for `VAULT_API_KEY` and `LICENSE_SIGNING_SECRET`. In Base44, store only the `VAULT_API_KEY` value as `VAULT_API_SECRET`; never expose the license-signing secret to the website.

License format: `420V-AAAA-BBBB-CCCC-DDDD-EEEE-<16 hex chars>`. The 20-character serial is HMAC-SHA256 signed with `LICENSE_SIGNING_SECRET`; the first 16 uppercase hex characters of the digest are appended. Activation requires BOTH a valid HMAC signature and a matching, active database record for the correct guild/user/subscription. A random or merely well-formatted key is rejected.

Base44 interoperability algorithm: concatenate the five 4-character serial groups (20 uppercase A-Z/0-9 characters), compute `HMAC-SHA256(secret, serial)`, hex-encode uppercase, take the first 16 characters, and append it after the final hyphen. Keep the secret server-side in Base44 secrets, never browser/client JavaScript.


## v3.2 Physical Vault / SQLite GUI
- `420_admin` -> **Vault Storage** opens the Vault Storage Manager.
- **Configure Path** accepts any accessible local, external, or network path. Saving a valid path automatically performs the initial/incremental SQLite index.
- **Scan Changes** updates new/changed/deleted files without rescanning at search time. **Full Reindex** rebuilds the catalog.
- Files and folders are indexed separately; beat-production assets are categorized (audio, MIDI, projects such as FLP, presets/sound libraries, ZIP/RAR/7Z and other archives). Unknown files remain catalogued so useful assets are not silently lost.
- `420_search` combines the link library with the physical Vault and shows `F###` file IDs / `D###` folder IDs. **Send Vault Item** uploads a file or ZIPs a complete folder temporarily.
- Delivery uses Discord's current `guild.filesize_limit`; it never assumes Nitro. Oversized items are not attempted and the exact size/limit/overage is reported.
- A disconnected drive does not erase the SQLite index. Reconnect it and use **Scan Changes**.

## v3.3 Admin Dashboard
`420_admin` is now a multi-section Discord control panel. Use the category menu for Overview, Vault Storage, Search & Delivery, Channels & Roles, Licensing, Subscriptions, Payments, Transactions, Security, Logs, and Diagnostics. Each section exposes buttons/modals/selectors for its supported settings. Vault path configuration automatically performs initial SQLite indexing when a valid path is saved.

## v3.4 entitlement + payment approval update
- New licenses use `420V-XXXX-XXXX-XXXX`; full HMAC-SHA256 authentication is stored server-side in SQLite.
- Access is entitlement-first: a bound/activated license alone is not sufficient. Paid subscriptions create subscription entitlements; `420_addlicense @user <days>` creates an explicit audited `admin_grant` entitlement.
- Cash App/manual checkout creates a private `420 PAYMENT APPROVALS` ticket. The customer can attach proof; administrators get Approve / Reject / Request Info / Close controls. Approval atomically creates the paid subscription, entitlement, short signed license, and activation DM.
- Pending ticket views and DM activation views are re-registered after bot restarts.

## v3.9 reliability fixes
- Full Terms are paginated; no 3,900-character truncation.
- TOS acceptance is persisted only after Verified-role assignment succeeds; guild/member are revalidated at final acceptance.
- One TOS panel message is edited/reused per guild.
- TOS disable clears the Unverified channel-overwrite gate and reconciles roles; old Terms versions force role re-verification when enabled.
- Canonical `check_access()` defines TOS/admin/Beta/license access. Beta Tester bypasses paid licensing only, not TOS. Vault Overseer is bot-admin.
- Subscription lifecycle now separates `billing_period_end` from `grace_until`; grace is anchored to the billing-period end and is not recursively extended.
- PayPal successful renewals fetch the provider subscription and use PayPal `billing_info.next_billing_time` as the new period boundary.
- Subscription activation, pending fulfillment, and manual payment approval use SQLite `BEGIN IMMEDIATE` transactions. Manual approval is idempotent.
- Vault search now uses FTS5 and scans update FTS incrementally instead of rebuilding the entire index after each scan.
- TOS numeric settings validate ranges; duplicate TOS schema declarations removed; schema version advanced to 9 and legacy migration backup tables are preserved.

## v3.10 automatic Discord bootstrap
On first join (and idempotently on startup), 420Vault creates/reuses the standard content channels plus `license`, `logs`, and `tickets`. The license channel receives the persistent activation panel; issued licenses are also delivered by DM with their per-license activation button. `logs` receives command/errors/bootstrap/ticket operational events. `tickets` receives a persistent 420Bot Support Center panel for crash/startup problems, bugs, Vault resource requests, feature/general requests, and Other. Payment/review tickets share the `420 BOT TICKETS` private-ticket category.

## v3.11 — Base44 Website API
v3.11 adds an authenticated server-to-server website API on the existing aiohttp listener. Set `API_ENABLED=1` and expose the listener to Base44 only through HTTPS. Base44 must store the same `VAULT_API_KEY` as a server-side secret and send it as a Bearer token. User routes also require `X-Guild-ID` and `X-Discord-User-ID`; admin routes verify the acting Discord user is a current bot admin/Vault Overseer. See `base44_reference/` for the exact feature map, access rules, schema summary and OpenAPI contract. The API can generate real admin-grant licenses through the bot's own licensing service, resend activation DMs, create real Discord support tickets, and read user/admin state. Payment checkout creation is intentionally not claimed as implemented yet.

## v3.12 — Physical Vault Search Browser
- `420_search` is the managed/internet Link Library browser and keeps its Search modal + pagination.
- `420_vault_search` is now a dedicated physical-Vault browser with the same Search-bar workflow.
- Physical Vault results are paginated and selectable; selecting a result delivers the file directly or safely ZIPs a folder when it fits the Discord upload limit.
- Internal Vault IDs remain supported by legacy commands for backward compatibility, but normal users no longer need to type IDs to download content.
- Vault searches use the indexed SQLite/FTS catalog and do not recursively rescan the physical drive when paging/searching.


## v3.13 Reliability Hardening

- Centralizes Discord administrator/Vault Overseer detection in `app/core/security.py`; `check_access()` now consumes the same authority.
- Adds atomic webhook claiming so simultaneous duplicate Stripe/PayPal deliveries cannot both run fulfillment. Failed/stale webhook work can be retried.
- Improves Stripe refund/dispute correlation back to the original transaction/subscription and records `refunded`/`disputed` review states.
- Moves Physical Vault GUI searches off the Discord event-loop thread and adds async database helper methods for continued migration of blocking DB paths.
- Enables SQLite busy timeout/foreign-key checks on runtime connections.
- Separates `VAULT_API_KEY` from `LICENSE_SIGNING_SECRET`; Base44 must use only `VAULT_API_KEY`.
- Adds `run_forever.bat` for crash restart and `scripts/healthcheck.py` for external uptime probes.

For public paid production, a local PC/tunnel remains a single-host dependency. Use the included restart/health tooling for beta operation, and move payment/webhook authority to always-on infrastructure before relying on it for general-public sales.

## v3.14 — Google Drive Search

420VaultBot now supports a third independent search source: `420_drive_search`. Administrators configure a Google Drive root folder with `420_drive_config <folder URL or ID>` and build the metadata-only index with `420_drive_sync`. Users get a Discord GUI with a search bar, paginated results, folder browsing, and direct file delivery when the file fits the guild's Discord upload limit. Oversized files receive an **Open in Google Drive** action instead of being downloaded through the bot.

Google Drive OAuth uses `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`, and `GOOGLE_DRIVE_REFRESH_TOKEN`. The authenticated Google account must already have permission to the configured root folder, including Shared-with-me folders. The sync stores metadata and IDs, not file contents, so large Drive collections do not need to be copied locally just to search them.


## v3.15.0 — Automatic Terms Onboarding
- Automatically creates/reuses `#terms` during server bootstrap.
- Stores the Terms channel as `tos_channel_id` and automatically publishes/repairs the persistent Terms verification panel.
- Discord Administrators, configured bot administrators, and Vault Overseers bypass the Terms gate so administration cannot be locked out during setup.
- Normal members still require the current Terms acceptance when the gate is enabled.

## v4.0.0 — Onboarding & Access System

420VaultBot v4 introduces automatic member onboarding. The server bootstrap creates/reuses the `#terms` channel and the Verified, Unverified, Subscribed, Beta Tester, and Vault Overseer roles. Normal new members are assigned Unverified, restricted from normal server channels, and directed by DM to the Terms channel with an **Open Terms & Verify** button. After successful verification, Unverified is removed and Verified is granted. Discord Administrators, configured bot administrators, and Vault Overseers bypass the TOS/onboarding gate. Discord does not provide bots an API to force-open a channel in another user's client, so the bot uses permissions plus a direct channel link as the reliable redirect mechanism.


## v4.0.1 — Google Drive Admin GUI
Google Drive Search configuration is now available directly in `420_admin` under **Google Drive**. Admins can configure the root folder, test the connection, sync metadata, view status, and disconnect the source without relying on typed Drive configuration commands. OAuth client credentials remain environment-only secrets and are never displayed or stored through Discord UI. `420_drive_config` without an argument now opens the Google Drive admin panel; the legacy URL/ID argument remains supported for compatibility.

## v4.0.2 — staged Google Drive setup
Google Drive admin configuration can now be completed in any order. **Save Drive Folder** stores the folder URL/ID without making a Google API call, so it works before OAuth is configured. **OAuth Setup** stores the client ID, client secret, and refresh token in a local secret file (or existing environment variables can still be used). **Test Connection** is the explicit point where 420Vault validates OAuth and confirms access to the saved folder. Sync remains separate and only runs after setup succeeds.

## v4.6.0 — Non-blocking indexing reliability
- Google Drive metadata sync now starts as a background job and acknowledges Discord immediately.
- Google Drive SQLite page writes and final FTS rebuild run off the Discord event loop.
- Drive Status reports live indexed count, elapsed time, current folder/finalization state, and failures.
- Duplicate Google Drive sync jobs are blocked per server.
- Physical Vault initial indexing, Scan Changes, and Full Reindex now run as background jobs with progress available through Stats.
- Duplicate physical Vault scans are blocked per server.
- Logging format setup was moved out of the heartbeat stack line to prevent the secondary percent-format logging failure seen while reporting blocked heartbeats.

## v4.7.0 — Physical Vault responsiveness hardening
- Physical Vault indexing commits in bounded batches instead of holding SQLite write locks for an entire drive scan.
- Removable-drive path checks run off the Discord event loop.
- Admin Vault panel no longer probes removable storage while rendering.
- Guild settings reads no longer request a SQLite writer lock on every read.
- SQLite busy timeout reduced to prevent long UI stalls; WAL/NORMAL enabled per connection.
- Legacy Vault path/list/download filesystem probes moved off the event loop.
- Admin GUI version footer updated to v4.7.0.

## v4.8.0 responsiveness overhaul

v4.8 moves long Google Drive and removable-storage work away from Discord's event-loop thread. Google Drive metadata pages are written in bounded SQLite batches, stale-item marking and FTS rebuilding are chunked, Drive browser queries run in worker threads, legacy Drive sync starts as a background job, and SQLite no longer renegotiates WAL mode on every connection. Physical Vault delivery/validation and diagnostics also avoid blocking the event loop. Status/progress remains available while background indexing is active.

## v5.5.6 reliability and delivery update

v5.5.6 adds the SQLite concurrency fix, immediate live scraper dashboard, strict restricted-account command surface, Physical Vault listen-before-download audio actions, Google Drive archive/folder delivery, a persistent `#license-generator` customer-selection GUI with Order IDs, and the bundled complete user PDF manual. See `V5.5.6-UPGRADE.txt`.
