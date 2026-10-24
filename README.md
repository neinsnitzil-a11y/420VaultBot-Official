# 🎛️ 420VaultBot

### Discord Music-Production Vault, Licensing, Subscription, Search & Community Platform

**Current release:** `v6.4.3`  
**Primary command prefix:** `420_`  
**Primary interface:** Discord message commands + buttons, selects and modals  
**Database:** SQLite + FTS-backed search/index data  
**Storage sources:** Physical/local/external/network Vault, Google Drive, managed link library, HTTPS remote manifests

420VaultBot is a modular Discord application built for music-production communities that need more than a basic file bot. It combines indexed music assets, Google Drive search, link discovery, audio previews, account authentication, public producer profiles, licensing, subscriptions, payments, Terms verification, support tickets, admin configuration, backups and update tooling in one system.

> **Important:** 420VaultBot is a software platform. It does not grant rights to redistribute copyrighted files, plugins, samples, presets, software or archives. Only use content you are authorized to host, index, distribute or link to.

---

## 📑 Table of Contents

- [What 420VaultBot Does](#-what-420vaultbot-does)
- [Main Features](#-main-features)
- [Requirements](#-requirements)
- [Installation](#-installation)
- [Initial Discord Setup](#-initial-discord-setup)
- [420_admin Full Setup Guide](#-420_admin-full-setup-guide)
- [Physical Vault Setup](#-physical-vault-setup)
- [Google Drive Setup](#-google-drive-setup)
- [Link Library & Scraper](#-link-library--scraper)
- [Remote File Servers](#-remote-file-servers)
- [Accounts, Profiles & 2FA](#-accounts-profiles--2fa)
- [Terms & Verification](#-terms--verification)
- [Licensing](#-licensing)
- [Subscriptions & Plans](#-subscriptions--plans)
- [Payment Providers](#-payment-providers)
- [Stripe Setup](#-stripe-setup)
- [PayPal Setup](#-paypal-setup)
- [Cash App / Manual Payments](#-cash-app--manual-payments)
- [Webhooks](#-webhooks)
- [Audio Previews](#-audio-previews)
- [Security & Antivirus](#-security--antivirus)
- [Backups, Updates & Recovery](#-backups-updates--recovery)
- [Website / API Integration](#-website--api-integration)
- [All Commands](#-all-commands)
- [Environment Variables](#-environment-variables)
- [Patch Notes: v6.2.x → v6.4.3](#-patch-notes-v62x--v643)
- [Troubleshooting](#-troubleshooting)
- [Security Notes](#-security-notes)

---

# 🌿 What 420VaultBot Does

420VaultBot provides four separate searchable resource systems:

1. **Managed Link Library** — `420_search`
2. **Physical Vault** — `420_vault_search`
3. **Google Drive** — `420_drive_search`
4. **Remote Server Library** — `420_server_search`

It also includes:

- Account login/authentication
- Authenticator-based 2FA
- Public/private producer profiles
- Searchable public profiles
- Terms of Service onboarding
- Role-based access control
- Signed license keys
- Subscription plans
- Stripe checkout
- PayPal subscriptions
- Cash App/manual approval workflows
- Payment tickets
- Support tickets
- Link antivirus integrations
- Attachment antivirus support
- Google Drive metadata indexing
- ZIP/RAR filename parsing for Drive archives
- Physical Vault audio preview support
- Admin GUI
- Update and recovery controls
- Backups and backup verification
- Audit logs
- Diagnostics
- Server export
- Authenticated website/API support

---

# ✨ Main Features

## 🎛️ Interactive Discord Command Center

Run:

```text
420_help
```

The bot provides a button-driven command directory instead of requiring users to memorize every command.

The existing `420_` message commands remain functional behind the GUI.

---

## 🔎 Unified Search Ecosystem

420VaultBot keeps separate search engines for different content sources instead of pretending every source is the same.

### Link Library

```text
420_search <query>
```

Features include:

- Paginated results
- Managed imported lists
- Scraper-created lists
- URL deduplication
- Search by website/domain
- Available-site discovery
- Link preview workflow
- Optional URL antivirus checks

### Physical Vault

```text
420_vault_search <query>
```

The physical Vault uses a persistent index instead of rescanning the drive on every query.

### Google Drive

```text
420_drive_search
```

Google Drive search works from synchronized metadata rather than redownloading the entire Drive for each query.

### Remote Server Search

```text
420_server_search
```

The current remote-source implementation uses an HTTPS JSON manifest and can use an optional bearer token.

---

# 💻 Requirements

Recommended environment:

- Windows 10/11 for the included `.bat` scripts
- Python 3.12
- Discord bot application/token
- Message Content Intent enabled in Discord Developer Portal
- Internet connection
- Storage access for the configured Vault
- FFmpeg if you want transcoded/optimized audio preview behavior
- Provider accounts if using Stripe, PayPal or Google Drive

The Python dependencies are listed in:

```text
requirements.txt
```

---

# 📦 Installation

## Fresh install

1. Extract the release ZIP.
2. Open the extracted `420VaultBot_v6.4.3` folder.
3. Run:

```text
install.bat
```

or:

```text
install_and_run.bat
```

4. Configure your Discord token and required secrets.
5. Start the bot with:

```text
run.bat
```

For an always-running/restart-oriented Windows setup, the package also contains:

```text
run_forever.bat
run_420vault_watchdog.bat
```

## Existing installation upgrade

**Back up first.**

Use:

```text
upgrade_existing.bat
```

The upgrade workflow is designed to preserve runtime data such as:

```text
.env
data/
config/
linklists/
credentials/
google_drive/
vault_index/
preview_cache/
backups/
logs/
```

Do not replace your live database or `.env` with a blank release copy.

---

# 🧰 Initial Discord Setup

Once the bot is online:

```text
420_version
420_setup
420_admin
420_diagnostics
```

## `420_setup`

The quick setup panel configures the most important mappings:

- Allowed search/delivery channels
- License activation channel
- Audit/log channel
- Vault administrator role
- Licensed member role

Normal users are restricted to the configured user/search channels. Admin management commands can be used outside those user channels.

---

# 🛠️ `420_admin` Full Setup Guide

Run:

```text
420_admin
```

The Admin GUI currently contains these sections:

- 🏠 Overview
- 💾 Vault Storage
- ☁️ Google Drive
- 🔎 Search & Delivery
- 🔗 Link Library & Scraper
- 🖥️ Remote File Servers
- 📺 Channels
- 👥 Access Roles
- 📜 Terms & Verification
- 🔑 Licensing
- 📅 Subscriptions
- 💳 Payments
- 🧾 Transactions
- 🛡️ Security
- 📜 Logs
- 🔊 Audio Previews
- ⬆️ Updates & Recovery
- 🩺 Diagnostics

## 🏠 Overview

Use this page to inspect:

- Vault configuration state
- Indexed file/folder totals
- Download status
- Licensing state
- Search pagination/max-result settings
- Subscription plan count
- Google Drive indexed size/count
- Link Library total

Buttons:

- **Refresh**
- **Library Stats**

---

## 💾 Vault Storage

Buttons:

- **Configure Path**
- **Test**
- **Scan Changes**
- **Full Reindex**
- **Stats**

Configure any path accessible to the bot process, for example:

```text
E:\Music Vault
D:\Drumkits
C:\Producer Resources
\\NAS\420Vault
```

### Scan Changes

Use this for normal maintenance. It updates the persistent Vault catalog without forcing a complete rebuild every time.

### Full Reindex

Use this if the index is damaged or you intentionally want to rebuild it.

### Important behavior

A disconnected drive should not be treated as permission to destroy the index. v6.4.2 also fixes the reconnect case where unchanged files could remain falsely marked unavailable after the drive returned.

---

# 💾 Physical Vault Setup

The Vault can index files and folders on local, external and accessible network storage.

Supported use cases include:

- WAV/MP3 audio
- AIFF and other indexed music assets
- MIDI
- FLP/project resources
- Presets and banks
- Drumkits
- Loops
- ZIP/RAR/7Z archives
- Folders
- Other production resources

## Search commands

```text
420_vault_search <query>
420_vault_search_type <extension>
420_vault_search_size <operator> <size> [limit] [page]
420_vault_search_terms <terms>
420_vault_random <count>
420_vault_stats
420_vault_list [path] [page]
420_download_vault <id>
```

## Admin Vault commands

```text
420_vault_path <folder>
420_reindex_vault
420_admin_delete_vault_index
```

`420_admin_delete_vault_index` deletes the guild's search index only. It does **not** delete the physical files.

---

# ☁️ Google Drive Setup

In:

```text
420_admin → Google Drive
```

Buttons include:

- **Save Drive Folder**
- **OAuth Setup**
- **Test Connection**
- **Sync Metadata**
- **Status**
- **Parse ZIP/RAR**
- **Disconnect**

## OAuth values

420VaultBot expects:

- Google OAuth Client ID
- Google OAuth Client Secret
- Google OAuth Refresh Token

The bot can read these from its local Drive secret file or environment configuration.

Relevant environment variables:

```dotenv
GOOGLE_DRIVE_CLIENT_ID=
GOOGLE_DRIVE_CLIENT_SECRET=
GOOGLE_DRIVE_REFRESH_TOKEN=
GOOGLE_DRIVE_SECRET_FILE=
```

## Recommended OAuth flow

1. Create a Google Cloud project.
2. Enable Google Drive API.
3. Configure Google Auth Platform.
4. Create a Web OAuth client.
5. Add this redirect URI when using OAuth Playground:

```text
https://developers.google.com/oauthplayground
```

6. Use your own OAuth credentials in OAuth Playground.
7. Request only the Drive scope your installation actually needs.
8. Generate a refresh token.
9. Enter the three matching values in **420_admin → Google Drive → OAuth Setup**.
10. Click **Test Connection**.
11. Save the Drive folder.
12. Click **Sync Metadata**.
13. Use **Status** to watch progress.

## Access-token expiration

Google access tokens normally expire after about one hour. That is expected. The bot uses the saved refresh token to request replacement access tokens.

The OAuth Playground's `Auto-refresh` checkbox only affects Playground — it does not control the bot.

## Drive archive parsing

**Parse ZIP/RAR** temporarily downloads eligible archives, indexes filenames inside them, and removes the temporary copy afterward.

The default archive parse maximum is controlled by:

```dotenv
GOOGLE_DRIVE_ARCHIVE_PARSE_MAX_BYTES=
```

The code defaults to 2 GiB if the variable is not set.

---

# 🔗 Link Library & Scraper

Admin section:

```text
420_admin → Link Library & Scraper
```

Buttons:

- New Web Scrape
- Upload TXT
- Import Sitemap
- Managed Lists
- Recent Jobs
- Configure Link AV
- Test Link AV
- Link AV Status
- Remove Bad Link(s)
- Discord Upload AV

The link pipeline supports bundled and managed lists such as:

```text
lists.txt
lists_part_2.txt
lists_part_3.txt
lists_part_4.txt
links_part_5.txt
links_part_6.txt
...
```

The index is deduplicated for runtime search.

## Link commands

```text
420_search <query>
420_search_site <domain> [query]
420_sendlink <...>
420_importlinks <name>
420_reloadlinks
420_sources
```

---

# 🖥️ Remote File Servers

Admin section:

```text
420_admin → Remote File Servers
```

Buttons:

- Add / Update Server
- Test & Sync
- Server List

The current implementation uses an **HTTPS JSON manifest** with an optional bearer token.

Use:

```text
420_server_search
```

Do not document arbitrary SMB/SFTP mounting as implemented unless you add that functionality separately.

---

# 👤 Accounts, Profiles & 2FA

## Account commands

```text
420_auth
420_logout
420_profile
420_profile_search
```

420VaultBot contains an account/session layer in addition to Discord membership.

Account features include:

- Login/session handling
- Email verification workflow
- Authenticator-based 2FA
- Public/private profile visibility
- Profile bio
- DAW
- Creator/artist identity
- Genres
- Website
- Socials
- Interests
- Timezone
- Member-since information

## Public profile search — v6.4.3

Run:

```text
420_profile_search
```

or:

```text
420_profile_search <query>
```

Users can search public profiles by public-facing fields such as name, genre or DAW.

Private profiles are excluded from the search query.

Security, email, license and subscription details must never be shown in someone else's public profile.

---

# 📜 Terms & Verification

Run:

```text
420_tos
```

or use the persistent Terms channel panel.

The Terms workflow includes:

- Paginated Terms content
- Configurable minimum read time
- Randomized knowledge check
- Five-question sample per attempt
- Randomized answer order
- Configurable pass percentage
- Explicit acceptance
- Role assignment
- Terms-version storage
- Re-verification when the configured Terms version changes

Important behavior:

- Acceptance is saved only after required role assignment succeeds.
- Beta Tester access may bypass payment depending on configuration, but should not bypass required Terms acceptance.

---

# 🔑 Licensing

420VaultBot uses signed licenses and server-side records.

License signing uses:

```text
HMAC-SHA256
```

Recommended secret:

```dotenv
LICENSE_SIGNING_SECRET=<strong random secret>
```

The bot can also fall back to `VAULT_API_KEY` for signing if no dedicated signing secret is configured, but a separate signing secret is strongly recommended.

## License workflow

There is no normal text activation command.

An issued license can be delivered to the assigned user through Discord DM with an **Activate License** button.

A persistent activation panel can also live in the configured License channel.

## Admin commands

```text
420_addlicense @user <days>
420_resendlicense <...>
420_revokelicense <...>
420_showlicense <...>
420_listlicenses
420_resetuserlicenses <...>
```

Use `0` days with `420_addlicense` only when you intentionally want a lifetime administrator grant.

Do not post full license keys publicly.

---

# 📅 Subscriptions & Plans

User commands:

```text
420_subscribe
420_subscription
```

Default plans currently seeded by the bot:

| Plan | Price | Duration |
|---|---:|---:|
| 1 Month | $25 | 30 days |
| 3 Months | $75 | 90 days |
| 6 Months | $100 | 182 days |
| 1 Year | $150 | 365 days |
| 2 Years | $200 | 730 days |
| 3 Years | $250 | 1095 days |
| Lifetime | $500 | No automatic expiry |

These values are editable in:

```text
420_admin → Subscriptions
```

Buttons:

- **Create / Update Plan**
- **Plan List**

Each plan can store/configure:

- Name
- Description
- Price
- Currency
- Duration
- Lifetime flag
- Grace days
- Enabled/disabled state
- Role mapping
- Features text
- Auto-renew behavior
- Provider availability
- Stripe Price ID
- PayPal Plan ID

---

# 💳 Payment Providers

420VaultBot currently supports three payment paths:

- Stripe
- PayPal
- Cash App/manual approval

Open:

```text
420_admin → Payments
```

Buttons:

- **Cash App**
- **Toggle Stripe**
- **Toggle PayPal**
- **Provider Status**

The bot intentionally does not store raw payment-card numbers or CVVs.

Stripe card entry occurs on Stripe-hosted checkout.

---

# 💳 Stripe Setup

## 1. Create your Stripe account

Create/configure your Stripe account and products/prices in Stripe Dashboard.

## 2. Add secrets to `.env`

```dotenv
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
PAYMENT_RETURN_URL=https://your-return-page.example/
```

`PAYMENT_RETURN_URL` is used for Stripe Checkout success/cancel redirects. If absent, the code falls back to Discord's app URL.

## 3. Create a Stripe Price for each plan

In Stripe Dashboard, create recurring prices for subscription plans and a one-time price for Lifetime if desired.

Copy each Stripe Price ID, for example:

```text
price_1234567890
```

## 4. Configure the plan

Go to:

```text
420_admin → Subscriptions → Create / Update Plan
```

Enter the matching Stripe Price ID for the plan.

## 5. Enable Stripe

Go to:

```text
420_admin → Payments → Toggle Stripe
```

Then use **Provider Status** to confirm the secret is detected.

## 6. Configure the webhook

Your public webhook URL should point to:

```text
https://YOUR-DOMAIN/webhooks/stripe
```

Set the signing secret returned by Stripe as:

```dotenv
STRIPE_WEBHOOK_SECRET=whsec_...
```

The webhook handler verifies Stripe signatures and keeps an idempotency/event table so duplicate provider deliveries do not fulfill the same payment twice.

---

# 🅿️ PayPal Setup

## 1. Create a PayPal developer application

Obtain:

- Client ID
- Client Secret

## 2. Configure `.env`

For sandbox testing:

```dotenv
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_SANDBOX=1
PAYPAL_WEBHOOK_ID=
```

For live mode:

```dotenv
PAYPAL_SANDBOX=0
```

## 3. Create PayPal subscription plans

Each non-Cash-App plan that should support PayPal needs a matching PayPal Plan ID.

Configure it from:

```text
420_admin → Subscriptions → Create / Update Plan
```

## 4. Enable PayPal

```text
420_admin → Payments → Toggle PayPal
```

Use **Provider Status** to confirm credentials are present.

## 5. Configure PayPal webhook

Point PayPal to:

```text
https://YOUR-DOMAIN/webhooks/paypal
```

Store the PayPal webhook ID in:

```dotenv
PAYPAL_WEBHOOK_ID=
```

The bot verifies webhook signatures with PayPal before processing events.

---

# 💵 Cash App / Manual Payments

Cash App does not use automated checkout in this build.

Configure it from:

```text
420_admin → Payments → Cash App
```

Set:

- Cashtag
- Payment instructions

When a member chooses **Cash App (Manual)**:

1. The bot creates a pending transaction.
2. A private payment ticket is created.
3. The user receives the amount and a transaction reference such as:

```text
420-123
```

4. The user uploads proof in the ticket.
5. An admin approves or rejects the payment.
6. Access is not granted until approval succeeds.

Admin command:

```text
420_approvepayment <transaction_id>
```

Admin GUI:

```text
420_admin → Transactions
```

Buttons:

- Recent Transactions
- Pending Manual

---

# 🌐 Webhooks

The embedded HTTP service can expose:

```text
/webhooks/stripe
/webhooks/paypal
/health
```

Relevant environment variables:

```dotenv
WEBHOOK_ENABLED=1
WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=8420
```

For real payment processing, expose the listener through HTTPS using a proper reverse proxy/tunnel and configure the provider webhook URL to the public HTTPS address.

Do not expose an unauthenticated local management service directly to the Internet.

---

# 🔊 Audio Previews

Admin section:

```text
420_admin → Audio Previews
```

Buttons:

- Preview Settings
- Toggle Previews
- Clear Preview Cache

The current user-manual behavior treats `.wav` and `.mp3` as directly auditionable formats.

Audio previewing is separate from downloading the original file.

Discord controls the audio player and playback UI.

Preview cache is stored under the application's data directory and can be cleared from the Admin GUI.

---

# 🛡️ Security & Antivirus

Admin section:

```text
420_admin → Security
```

Controls include:

- Configure Link AV
- Link AV Status
- Test Link AV
- Add Link(s)
- Remove Bad Link(s)
- Configure Upload AV
- Test Upload AV
- Upload AV Status
- Reconfigure SMTP
- Toggle Licensing
- Security Status

## Link Antivirus

Supported configuration references include:

```dotenv
URLHAUS_AUTH_KEY=
METADEFENDER_API_KEY=
```

The scraper does not automatically submit every discovered link for antivirus scanning. Scanning is an explicit/admin workflow.

## Discord upload antivirus

The attachment scanner can be configured to use:

- Microsoft Defender
- ClamAV

The executable path and size limits are configurable from the Admin GUI.

## SMTP / account email

SMTP can be configured through the account/admin security interface and corresponding environment variables.

Relevant variables include:

```dotenv
AUTH_SMTP_HOST=
AUTH_SMTP_PORT=587
AUTH_SMTP_USER=
AUTH_SMTP_PASSWORD=
AUTH_FROM_EMAIL=
AUTH_SMTP_SSL=0
```

---

# 💾 Backups, Updates & Recovery

Admin section:

```text
420_admin → Updates & Recovery
```

Buttons:

- **Install Update**
- **Restart Bot**
- **Backup Now**
- **Backup History**
- **Verify Latest**
- **Restore Backup**

v6.4.1 changed the backup interaction so Discord is acknowledged before long backup work begins, preventing the common `420VaultBot didn't respond in time` message while the backup actually succeeds.

The updater preserves important runtime data and creates backups before application code replacement.

For major production updates, a stopped/offline update using `upgrade_existing.bat` is still the safer path.

---

# 🌐 Website / API Integration

420VaultBot includes an authenticated server-to-server HTTP API.

It uses:

```dotenv
VAULT_API_KEY=<long random server-side secret>
API_ENABLED=1
```

Authentication accepts a bearer token or supported service-key header.

The API exposes routes for:

- Bot status
- Plans
- Current user/account state
- User licenses
- License resend
- User subscriptions
- User transactions
- Tickets
- Ticket creation
- Admin users
- Admin licenses
- Admin license creation
- Admin license revocation
- Admin subscriptions
- Admin transactions
- Admin tickets
- Admin logs
- Admin Vault status

Example route set:

```text
GET  /api/v1/status
GET  /api/v1/plans
GET  /api/v1/me
GET  /api/v1/licenses/me
POST /api/v1/licenses/resend
GET  /api/v1/subscriptions/me
GET  /api/v1/payments/me
GET  /api/v1/tickets
POST /api/v1/tickets
GET  /api/v1/admin/users
GET  /api/v1/admin/licenses
POST /api/v1/admin/licenses
POST /api/v1/admin/licenses/{code}/revoke
GET  /api/v1/admin/subscriptions
GET  /api/v1/admin/transactions
GET  /api/v1/admin/tickets
GET  /api/v1/admin/logs
GET  /api/v1/admin/vault
```

Never expose `VAULT_API_KEY` in browser JavaScript.

---

# ⌨️ All Commands

The registered message-command prefix is `420_`.

## Account / Profile

```text
420_auth
420_logout
420_profile
420_profile_search
```

## Help / Documentation

```text
420_help
420_user_manual
420_admin_manual
420_features
420_sources
420_status
420_version
```

## Terms / Setup / Admin

```text
420_tos
420_setup
420_admin
420_diagnostics
420_showchannels
```

## Link Library

```text
420_search
420_search_site
420_sendlink
420_importlinks
420_reloadlinks
```

## Physical Vault

```text
420_vault_path
420_vault_search
420_vault_search_type
420_vault_search_size
420_vault_search_terms
420_vault_random
420_vault_stats
420_vault_list
420_download_vault
420_reindex_vault
420_admin_delete_vault_index
```

## Google Drive

```text
420_drive_search
420_drive_config
420_drive_sync
420_drive_status
```

## Remote Server Search

```text
420_server_search
```

## Server Controls

```text
420_lockdown
420_unlock
420_exportserver
```

## Licensing

```text
420_addlicense
420_resendlicense
420_revokelicense
420_showlicense
420_listlicenses
420_resetuserlicenses
```

## Subscription / Payments

```text
420_subscribe
420_subscription
420_approvepayment
```

> Command permissions vary by role, Terms state, licensing/subscription state and configured allowed channels.

---

# ⚙️ Environment Variables

A production `.env` may contain values such as:

```dotenv
# Discord
DISCORD_TOKEN=

# Licensing / website API
LICENSE_SIGNING_SECRET=
VAULT_API_KEY=

# Google Drive
GOOGLE_DRIVE_CLIENT_ID=
GOOGLE_DRIVE_CLIENT_SECRET=
GOOGLE_DRIVE_REFRESH_TOKEN=
GOOGLE_DRIVE_SECRET_FILE=data/google_drive_secrets.json
GOOGLE_DRIVE_ARCHIVE_PARSE_MAX_BYTES=2147483648

# Stripe
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
PAYMENT_RETURN_URL=https://discord.com/app

# PayPal
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_WEBHOOK_ID=
PAYPAL_SANDBOX=1

# HTTP / webhooks / API
WEBHOOK_ENABLED=0
API_ENABLED=0
AUTH_ENABLED=1
WEBHOOK_HOST=127.0.0.1
WEBHOOK_PORT=8420

# Account authentication / SMTP
AUTH_PUBLIC_BASE_URL=
AUTH_SMTP_HOST=
AUTH_SMTP_PORT=587
AUTH_SMTP_USER=
AUTH_SMTP_PASSWORD=
AUTH_FROM_EMAIL=
AUTH_SMTP_SSL=0
AUTH_LOCK_SECONDS=1800

# Link antivirus
URLHAUS_AUTH_KEY=
METADEFENDER_API_KEY=

# Watchdog
HEARTBEAT_INTERVAL_SECONDS=30
HEARTBEAT_PREVENT_SYSTEM_SLEEP=1
```

Do not commit real secrets to GitHub.

Recommended `.gitignore` exclusions include:

```text
.env
.venv/
data/
backups/
logs/
credentials/
google_drive/
preview_cache/
*.db
*.sqlite
*.sqlite3
*.sqlite-wal
*.sqlite-shm
```

---

# 🧪 Recommended First-Time Configuration Order

For a clean setup, configure the bot in this order:

1. **Discord token and intents**
2. `420_setup`
3. Allowed user/search channels
4. License channel
5. Log channel
6. Admin role
7. Licensed/member role
8. `420_admin → Access Roles`
9. Terms channel and Terms gate
10. Physical Vault path
11. Scan Changes / Full Reindex
12. Google Drive credentials and root folder
13. Drive metadata sync
14. Link Library / scraper
15. Remote file server if used
16. Subscription plans
17. Payment providers
18. Webhooks
19. SMTP/email authentication
20. Security/AV options
21. Audio preview settings
22. `420_diagnostics`
23. Test everything with a normal non-admin Discord account

---

# 🩹 Patch Notes: v6.2.x → v6.4.3

## v6.2.1 — Command Button Expansion

- Added clickable buttons for the active `420_` command set.
- Preserved typed command backends instead of replacing them.
- Expanded `420_help` into a button-driven command interface.

## v6.2.2 — Update/Data Preservation

- Improved preservation of persistent runtime data during updates.
- Protected accounts, sessions, licenses, profiles, 2FA data, `.env`, databases, Vault state, logs and runtime configuration from normal code updates.
- Avoided replacing existing security/encryption runtime data with fresh release copies.

## v6.2.3 — Command Center / Help Restoration

- Added/restored paginated `420_help` button navigation.
- Exposed more commands through the GUI.
- Preserved the existing `420_` command workflows.

## v6.2.4 — Channel Restriction & GUI Update

- Restricted normal-user commands to configured Audio Vault/search channels.
- Allowed administrators to use management controls in approved admin/testing areas.
- Closed the loophole where old buttons could bypass channel restrictions.
- Preserved the interactive Command Center.

## Regression after v6.2.4

A later build line unexpectedly identified itself as an older 6.1.x build and lost/restored portions of newer functionality. The recovery work focused on preserving:

- Command Center buttons
- Admin GUIs
- Public profiles
- 2FA
- Welcome/account flow
- Licensing/subscription code
- Correct version reporting

## v6.3.6 — Restored Build

- Restored the newer v6.2.4 interface as the baseline.
- Restored Command Center functionality.
- Restored Admin GUI functionality.
- Restored public profiles.
- Restored authenticator 2FA.
- Restored account welcome behavior from the older account build where needed.
- Corrected version-line confusion.

## v6.4.0 — Upgrade Safety

- Added downgrade protection.
- Added upgrade dry-run behavior.
- Added application-source backup behavior.
- Added stronger runtime-data preservation safeguards.
- Added regression checks intended to prevent future stripped/downgraded releases.

## v6.4.1 — Backup & Reliability Audit Fixes

- Fixed **Backup Now** completing on disk while Discord displayed `didn't respond in time`.
- Deferred/acknowledged the Discord interaction before doing slow backup work.
- Added completion follow-up messaging.
- Switched supported live SQLite backups to SQLite-native backup behavior.
- Improved unique backup naming.
- Added backup verification before reporting success.
- Added backup-manifest path validation.
- Corrected stale version labels in affected admin interfaces.
- Identified remaining synchronous SQLite/event-loop and updater rollback areas for future hardening.

## Google Drive Authentication Audit

During the v6.4.1 troubleshooting cycle:

- Verified the bot's token-refresh request structure.
- Identified weak OAuth error reporting that collapsed useful Google errors into generic `Unauthorized` messages.
- Identified possible confusion from relative Drive credential-file paths.
- Identified per-field fallback behavior that could mix JSON and environment credentials if configuration is incomplete.
- Confirmed a working Google OAuth refresh-token flow after correcting the OAuth credential set.

## v6.4.2 — Physical Vault Reconnect & Download Repair

- Fixed rescanned unchanged files remaining marked unavailable after an external drive reconnect.
- Added repaired path resolution under the currently configured Vault root.
- Improved behavior when the configured Vault root/drive path changes.
- Applied repaired path handling to Vault download/preview flows.
- Filtered common junk metadata such as `.DS_Store`.
- Filtered unavailable records from normal Vault results.
- Kept path resolution restricted to the configured Vault root.

## v6.4.3 — Public Profile Search

- Added `420_profile_search`.
- Added public-profile discovery by public-facing profile fields.
- Added paginated profile results.
- Added a public-profile search entry in the Help/Command Center interface.
- Restricted results to the same Discord guild.
- Excluded private profiles at query time.
- Reused the existing public profile card while keeping private account/security/license information out of public results.

---

# 🩺 Troubleshooting

## Bot is online but sometimes does not respond

Possible causes include:

- Slow filesystem operations
- SQLite contention
- Blocking work on the Discord event loop
- External API latency
- Stale GUI panels after an update
- Missing permissions
- A background task error

Run:

```text
420_diagnostics
```

Then check logs and retry using a freshly generated panel.

## Backup succeeds but Discord says the bot did not respond

Update to v6.4.1 or later. That interaction timing bug was patched.

## Vault item says unavailable even though the drive is connected

Use v6.4.2 or later.

Then:

1. Confirm the configured Vault root.
2. Click **Scan Changes**.
3. Open a fresh `420_vault_search` panel.

## Google Drive says Unauthorized

First test the same OAuth Client ID, Client Secret and refresh token with Google's token endpoint/OAuth Playground.

If Google accepts the refresh token but the bot does not, inspect which credential source the running bot is loading.

## Drive sync shows zero files

Check:

- Root folder configuration
- OAuth permissions
- Google Drive API enabled
- Test Connection
- Metadata sync status

## Audio preview unavailable

Possible reasons:

- Source file is offline
- Previewing is disabled
- File isn't treated as playable audio
- Upload limit exceeded
- FFmpeg/transcoding support is unavailable

## Commands only show a few options

The account may be in restricted mode.

Check:

- Terms acceptance
- License/subscription entitlement
- Beta Tester policy
- Allowed command channels

---

# 🔐 Security Notes

- Never publish `.env`.
- Never publish Discord tokens.
- Never publish Google OAuth refresh tokens.
- Never publish OAuth Client Secrets.
- Never publish Stripe/PayPal secrets.
- Never publish `LICENSE_SIGNING_SECRET`.
- Never publish `VAULT_API_KEY`.
- Rotate any secret shown in screenshots or committed to source history.
- Use HTTPS for public webhooks/API routes.
- Keep payment card collection on Stripe/PayPal hosted interfaces.
- Do not expose raw license keys in public profiles.
- Treat public profile fields separately from private account/security details.
- Keep backups protected because they may contain user/account data.

---

# 📜 License / Commercial Distribution

The runtime license system used by Discord members is separate from the legal license governing a purchaser of the source code.

A customer who buys the 420VaultBot source code is a **software purchaser/operator**, not automatically a subscriber/licensee of the Discord community where the original bot is hosted.

Use a separate commercial software license or source-code agreement to define:

- Installation rights
- Modification rights
- Resale restrictions
- Redistribution restrictions
- Number of production installations
- Support period
- Update entitlement
- Branding rights
- Liability limitations

---

# 🎛️ 420VaultBot v6.4.3

**One bot. One Vault. Multiple resource sources. Full Discord administration.**

Built around indexed producer resources, configurable storage, role-aware access, licensing, subscriptions, payments, profiles, authentication and interactive Discord controls.
