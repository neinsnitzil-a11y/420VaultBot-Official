# 🎛️ 420VaultBot
### The All-in-One Discord Music Production Vault & Community Management Platform

**Current Release: v6.4.1 — Reliability & Recovery Update**

420VaultBot is a modular Discord application built for music producers, sound designers, sample-library administrators, and digital-content communities.

It combines physical file storage, indexed music libraries, Google Drive integration, audio previews, subscription management, secure licensing, account authentication, public profiles, interactive Discord interfaces, administrative controls, and update management into one ecosystem.

Unlike a conventional Discord file-sharing bot, 420VaultBot is designed to operate as a complete content management and membership platform.

---

## 🌟 Overview

420VaultBot helps Discord server owners manage large collections of music-production resources while controlling access to those resources through customizable user roles, licenses, and subscription plans.

The platform supports:

- 🎵 Physical music-production Vaults
- ☁️ Google Drive file indexing and searching
- 🔍 Searchable link libraries
- 🎧 Audio previews directly inside Discord
- 🗂️ File and folder browsing
- 🔐 Signed license activation
- 💳 Subscription and payment management
- 👤 User accounts and public profiles
- 🔑 Two-factor authentication
- 🛡️ Administrative permission controls
- 🖥️ Interactive Discord command panels
- 📋 Terms of Service verification
- 🎟️ Support and payment tickets
- 🔄 Application updates and backups
- 🌐 Authenticated website API integration
- 📊 Diagnostics and operational logging

**The goal is simple: provide the tools needed to manage a music-production community through one configurable application.**

---

# 📑 Table of Contents

1. What Makes 420VaultBot Different
2. Feature Overview
3. Discord Command Center
4. Physical Vault System
5. Google Drive Integration
6. Link Library
7. Audio Preview System
8. Licensing System
9. Subscriptions and Payments
10. User Accounts and Profiles
11. Two-Factor Authentication
12. Administrator Dashboard
13. Automatic Server Setup
14. Terms of Service
15. Website API Integration
16. Backup and Recovery
17. Installation
18. Configuration
19. Command Reference
20. Version 6.4.1 Release Notes
21. Security
22. Troubleshooting
23. Commercial Distribution
24. Known Limitations
25. Disclaimer

---

# 🚀 What Makes 420VaultBot Different?

Most Discord bots specialize in a limited set of functions.

A music bot plays music. A moderation bot manages members. A licensing bot verifies access. A file-sharing bot uploads attachments.

420VaultBot combines multiple systems into a single application.

Its architecture connects storage, discovery, identity, membership access, payments, and administrative operations.

### Integrated resource management

Physical files, Google Drive resources, and indexed links can be accessed through dedicated search workflows.

### Persistent searchable indexes

The physical Vault uses SQLite indexing rather than scanning the entire storage drive every time a user searches.

### User access management

Licenses, subscriptions, administrator grants, roles, and Terms of Service requirements work together to control access.

### Interactive navigation

Users can navigate supported operations through Discord buttons, select menus, and modal forms instead of memorizing dozens of commands.

### Configurable storage

Server owners are not restricted to a specific drive letter or directory name.

### Commercial deployment

The application includes administrative configuration, licensing workflows, payment integrations, backups, and update utilities suitable for further commercial development and deployment.

---

# 🎛️ Discord Command Center

420VaultBot includes a graphical control system built using Discord's interactive components.

The primary entry point is:

`420_help`

This command opens the interactive command directory.

The v6.2.4 implementation introduced a paginated button directory covering the registered command set.

Because Discord limits the number of message components, the command directory distributes controls across multiple pages.

### User interface categories

| Category | Function |
|---|---|
| Account & Help | Account access, profiles, documentation |
| Search & Browse | Resource discovery |
| Vault Tools | Physical Vault browsing and delivery |
| Access & Subscription | Licenses and subscription information |
| Admin Setup & System | Configuration and diagnostics |
| Admin Vault, Drive & Links | Storage and search administration |
| Admin Licensing & Payments | Membership and billing management |

Administrative controls are restricted by the bot's permission checks.

The original `420_` command workflows remain available.

**420VaultBot uses the `420_` message-command prefix rather than requiring slash commands for its primary interface.**

---

# 💾 Physical Vault Management

The physical Vault is one of the core components of 420VaultBot.

Administrators can configure a storage directory containing music-production resources.

Supported storage locations include:

- Internal hard drives
- External USB drives
- SSDs
- Network-mounted storage
- Accessible shared folders
- Custom local storage paths

The configured directory does not need to be named `420Vault`.

For example:

```text
E:\Music Production Vault
D:\Sound Libraries
C:\Production Assets
\\SERVER\AudioVault
```

The process running the bot must have permission to access the configured location.

## SQLite indexing

The Vault maintains a persistent SQLite-based catalog.

The indexed information is used to make search operations faster and avoid recursively scanning the physical drive on every request.

The implementation includes SQLite FTS5 support.

Available indexing operations include:

- Initial indexing
- Incremental scanning
- Full reindexing
- File metadata updates
- Deleted-file detection
- Folder indexing
- Search index maintenance

### Supported asset categories

The Vault is designed to catalog music-production resources, including:

| Category | Examples |
|---|---|
| Audio | WAV, MP3, AIFF |
| MIDI | MIDI files |
| Projects | FLP and other production-project resources |
| Presets | Synthesizer banks and sound presets |
| Drumkits | Drum samples and kit collections |
| Loops | Melody, drum, and instrument loops |
| Archives | ZIP, RAR, 7Z |
| Other files | Additional resources located in the configured Vault |

A file does not necessarily need to belong to a recognized category to appear in the catalog.

## Physical Vault GUI

Run:

`420_vault_search`

The dedicated browser provides search and pagination controls.

Users can select results without manually entering internal file identifiers.

### File delivery

For an individual file, the bot checks the available Discord upload limit before attempting delivery.

For a folder, the delivery workflow can create a temporary ZIP archive.

Oversized files are reported rather than blindly uploaded.

**Note:** Actual upload limits depend on the Discord server and applicable platform restrictions. Large-file external delivery is not guaranteed by the current release.

## External drive handling

A temporarily disconnected storage drive should not automatically erase its existing index.

When the drive reconnects, administrators can initiate an incremental scan.

---

# ☁️ Google Drive Integration

420VaultBot supports a separate Google Drive search system.

Administrators can configure a Google Drive root folder and synchronize its metadata.

### Features

- OAuth-based Google Drive access
- Configurable root folder
- Metadata indexing
- Paginated search results
- Folder browsing
- Drive connection testing
- Indexing progress information
- Background synchronization
- File delivery where supported
- Google Drive links for oversized resources

Large Google Drive collections do not need to be downloaded in full merely to build the metadata index.

### Configuration

Google Drive authentication uses:

```dotenv
GOOGLE_DRIVE_CLIENT_ID=
GOOGLE_DRIVE_CLIENT_SECRET=
GOOGLE_DRIVE_REFRESH_TOKEN=
```

These credentials should be stored securely in the bot's environment configuration.

The authenticated account must have permission to access the configured folder.

### Commands

`420_drive_config` — Configure the Google Drive root.

`420_drive_sync` — Synchronize the Drive index.

`420_drive_status` — Review synchronization information.

`420_drive_search` — Open the Drive search interface.

The Google Drive integration requires functioning credentials and network access.

---

# 🔗 Searchable Link Library

420VaultBot includes a managed link-library system.

This is useful for organizing approved external resources, documentation, music-production websites, and other indexed URLs.

### Features

- Searchable links
- Paginated results
- Link deduplication workflows
- Link-list management
- Administrator reindexing
- Combined resource-discovery workflows
- Existing scraper integration

The application includes link scraping and administrative link-management modules.

Only index resources you are authorized to access and distribute.

---

# 🎧 Audio Preview System

420VaultBot includes a listen-before-download workflow for supported audio files.

Users can preview supported resources directly through Discord attachments without manually downloading the full original file first.

### Supported workflows

- Audio preview actions
- Original-file download actions
- Cached preview generation
- FFmpeg-assisted MP3 previews for supported large audio
- Administrative preview-cache controls

The audio-preview system is intended for production sounds, loops, one-shots, and other compatible audio assets.

FFmpeg-dependent functionality requires a compatible FFmpeg installation.

Actual playback is handled by Discord's client and supported attachment formats.

---

# 🔐 Licensing System

420VaultBot implements license-based access management.

Administrators can issue licenses associated with users and access entitlements.

### License security

The implementation includes HMAC-SHA256 signing.

License validation is tied to server-side records and access state.

A license must satisfy applicable signature, record, user, guild, and entitlement checks.

Possessing a string that resembles a license key is not sufficient for access.

### License activation

The licensing system supports private Discord activation messages.

A generated license can be delivered through a DM containing an activation control.

A persistent license-entry panel is also part of the server onboarding workflow.

### Administrative licensing operations

Administrators can:

- Issue licenses
- Review license information
- Revoke licenses
- Resend activation messages
- Manage access entitlements
- Review subscription status
- Inspect licensing records

### Manual license grants

Administrative license grants are separate from paid subscription fulfillment.

This enables server owners to issue access manually where appropriate.

### Important distinction

The user-license system controls access for members of a server running 420VaultBot.

It is not the same thing as a commercial software license governing the purchaser's rights to the source code.

---

# 💳 Subscriptions and Payment Management

420VaultBot contains configurable subscription and payment-management components.

Supported payment workflows include:

| Provider | Integration approach |
|---|---|
| Stripe | Hosted checkout and verified webhooks |
| PayPal | Provider subscription and webhook integration |
| Cash App | Manual payments requiring administrator approval |

**Cash App payments are not automatically verified through a native Cash App payment API.**

The manual workflow requires administrator review.

## Subscription management

Administrators can configure subscription plans and their associated access rules.

The implementation includes mechanisms for:

- Subscription creation
- License issuance
- Entitlement management
- Renewal tracking
- Expiration handling
- Grace periods
- Manual payment approval
- Payment-related tickets
- Refund and dispute processing paths
- Subscription-access reconciliation

### Payment approval tickets

Manual payment submissions can be reviewed through private Discord tickets.

Administrative actions include approval, rejection, and requests for additional information.

The approval logic includes safeguards intended to avoid duplicate fulfillment.

## Payment security

420VaultBot is designed to delegate sensitive card collection to payment providers.

Raw credit card numbers and CVV values should never be collected or stored by the bot.

### Webhook configuration

The application exposes supported payment-webhook endpoints through its configured HTTP listener.

Examples:

```text
/webhooks/stripe
/webhooks/paypal
/health
```

For publicly accessible payment integrations, use HTTPS and configure the applicable webhook secrets.

A reverse proxy or tunnel may be used to route HTTPS traffic to the local service.

A stable, always-on deployment is strongly recommended for commercial payment processing.

---

# 👤 User Account System

420VaultBot includes account-management functionality separate from Discord's ordinary server membership controls.

The account system provides a foundation for authenticated features and account-related permissions.

### Account functionality

- Account registration workflows
- Login and authentication
- Profile management
- Account information
- Public profile discovery
- Account-related Discord interactions
- Login data preservation during updates

### Public profiles

Members can use the implemented public-profile workflows to discover other users.

Profile information and visibility should be managed according to the configured account permissions.

Private authentication and billing data must not be exposed through public profiles.

---

# 🔑 Two-Factor Authentication

The account-security system includes authenticator-based two-factor authentication.

This provides an additional authentication layer beyond an account password.

The current source contains dedicated account-security and authenticator-related functionality.

Administrators should verify account recovery and authentication flows before deploying them to paying customers.

### Security recommendations

- Use unique account passwords.
- Protect recovery information.
- Keep the application's secrets private.
- Do not distribute live session databases.
- Review authentication failures through authorized diagnostics.

---

# 🛡️ Administrative Dashboard

The main administrative entry point is:

`420_admin`

This opens an interactive management interface.

The available sections cover the application's core operations.

### Administrative categories

| Section | Purpose |
|---|---|
| Overview | System information |
| Vault Storage | Physical storage configuration |
| Search & Delivery | Search and download settings |
| Channels & Roles | Discord permissions and mappings |
| Licensing | License administration |
| Subscriptions | Plan and entitlement settings |
| Payments | Payment provider configuration |
| Transactions | Payment and fulfillment records |
| Security | Access and security controls |
| Logs | Operational events |
| Diagnostics | System troubleshooting |
| Updates & Recovery | Backups and application maintenance |

The interface uses buttons, menus, and supported modal dialogs.

Administrator access must be enforced through Discord permission checks, not simply by hiding buttons.

---

# 🏗️ Automatic Discord Server Setup

420VaultBot contains server-bootstrap functionality for creating or reusing supported channels and posting persistent panels.

Examples of managed channel purposes include:

- Music-production resource categories
- License activation
- Administrative logging
- Support tickets
- Terms of Service onboarding

The precise channels created depend on configuration and permissions.

The bootstrap process is designed to reuse existing configured resources rather than needlessly creating duplicates.

### Permission requirements

Depending on enabled features, the bot may require:

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Attach Files
- Manage Roles
- Manage Channels
- Manage Messages

Only grant permissions needed by your deployment.

The bot's role must be positioned appropriately for any roles it needs to assign.

---

# 📋 Terms of Service and Member Verification

420VaultBot contains a configurable Terms of Service onboarding system.

### Features

- Persistent Terms panel
- Paginated Terms content
- Member acceptance
- Verified-role assignment
- Acceptance-state tracking
- Terms-version checks
- Reverification after policy updates
- Administrator bypass rules

The implemented access rules distinguish between Terms verification and subscription entitlement.

For example, a Beta Tester entitlement does not automatically bypass a required Terms acceptance.

Terms-related disciplinary controls should follow Discord's policies. Discord bots do not receive ordinary members' IP addresses and cannot directly enforce IP bans.

---

# 🎟️ Support and Payment Tickets

420VaultBot includes ticket workflows for user requests and administrative review.

Examples include:

- Technical support
- Bug reports
- Vault resource requests
- General assistance
- Payment approval

Persistent panels provide access to supported ticket operations.

Ticket permissions should limit access to authorized users and staff.

---

# 🌐 Website and API Integration

420VaultBot includes an authenticated HTTP API designed for integration with external management websites.

The repository contains Base44 reference material, including an API contract and access documentation.

### API capabilities represented in the source

- Authenticated server-to-server requests
- Account-related information access
- Administrative authorization checks
- Licensing operations
- Discord support-ticket integration
- Selected bot-management operations

### Authentication

The API uses a dedicated secret:

```dotenv
VAULT_API_KEY=
```

This secret must be kept server-side.

Do not expose it in browser JavaScript.

The API secret must be separate from:

```dotenv
LICENSE_SIGNING_SECRET=
```

A website should not need access to the private license-signing secret merely to invoke authorized server-side operations.

**Note:** The presence of the API does not mean that a complete production website or every possible checkout endpoint is included in this Discord release.

Refer to `base44_reference/` for the documented API surface.

---

# 🔄 Backup, Update and Recovery

420VaultBot includes backup and update-management utilities.

The administrative recovery interface provides controls for:

- Installing updates
- Restarting the bot
- Creating backups
- Reviewing backup history
- Verifying backups
- Restoring backups

### Data preservation

The update workflow is designed to preserve important runtime information, including:

- Environment settings
- User accounts
- Login/session records
- License databases
- Subscription databases
- Vault indexes
- Google Drive configuration
- Link-list data
- Credentials
- Operational configuration
- Logs and backups

Keep a separate backup before every production update.

### Important update warning

The v6.4.1 source audit identified a limitation in the in-Discord updater's application-code rollback behavior.

For this release, the recommended production upgrade method is:

**Stop the bot and use `upgrade_existing.bat`.**

Do not rely exclusively on the in-Discord updater to recover an installation after a failed code replacement.

---

# 💻 Installation

## Requirements

- Windows with a supported Python environment
- Python 3.12 for the documented Windows bootstrap workflow
- A Discord bot token
- A Discord server where you have permission to configure the bot
- Internet connectivity for Discord and enabled external integrations
- Sufficient storage for the application, indexes, and configured Vault

Additional dependencies are listed in `requirements.txt`.

### Step 1 — Download

Download the release ZIP and extract it into a new folder.

For example:

```text
C:\420VaultBot\
```

### Step 2 — Run the installer

Open:

```text
install.bat
```

The documented installer attempts to bootstrap Python 3.12, prepare the Python environment, install dependencies, and launch the bot.

If Python installation requires elevated privileges or confirmation, follow the installer prompts.

### Step 3 — Configure Discord

Obtain your bot token from the Discord Developer Portal.

Configure the token through the application's supported setup procedure.

**Never publish your Discord token.**

Enable the privileged intents required by the bot's enabled features, including Message Content Intent for its message-command interface.

### Step 4 — Start the application

Use the supplied launcher:

```text
run.bat
```

Alternatively, the project includes:

```text
run_forever.bat
```

The latter is intended for a restart-oriented Windows deployment.

### Step 5 — Verify operation

Once the bot has connected to Discord, run:

```text
420_version
```

Then:

```text
420_help
```

For administrators:

```text
420_admin
```

Confirm that the expected interactive panels appear.

### Step 6 — Configure the Vault

Open the administrator dashboard and navigate to the Vault Storage controls.

Choose a directory the running bot can access.

Start indexing and check the reported progress.

### Step 7 — Configure optional integrations

Configure Google Drive, payment providers, website API access, and additional services only when required.

Do not expose an HTTP listener publicly until its authentication and deployment configuration have been reviewed.

---

# 🐧 Linux and Hosted Deployment

The source includes Python-based application components that may be deployed in a properly configured Linux environment.

However, the documented `.bat` installation and startup scripts are Windows-specific.

Linux installations require equivalent Python environment setup and process management.

For production hosting:

1. Use a compatible Python environment.
2. Install `requirements.txt`.
3. Provide the required configuration and secrets.
4. Ensure persistent storage is available.
5. Configure restart supervision.
6. Use HTTPS for public API and webhook endpoints.
7. Monitor application and integration health.

Linux deployment should be validated separately before being sold as a fully supported installation option.

---

# ⚙️ Configuration

The application relies on a combination of environment settings, persisted application configuration, and administrative controls.

An illustrative environment configuration is:

```dotenv
# Discord
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN

# Licensing
LICENSE_SIGNING_SECRET=YOUR_PRIVATE_SIGNING_SECRET

# Website API
VAULT_API_KEY=YOUR_PRIVATE_API_KEY
API_ENABLED=0

# Payment webhooks
WEBHOOK_ENABLED=0

# Google Drive
GOOGLE_DRIVE_CLIENT_ID=
GOOGLE_DRIVE_CLIENT_SECRET=
GOOGLE_DRIVE_REFRESH_TOKEN=
```

This example is not a complete configuration template.

Use the actual setup script and configuration definitions from the source for the full list of supported environment variables.

Do not replace previously generated secrets on an existing installation without planning how stored accounts, licenses, and encrypted settings will be affected.

### Never commit these files to a public repository

```text
.env
*.db
*.sqlite
*.sqlite3
*.sqlite-wal
*.sqlite-shm
.venv/
backups/
credentials.json
token.json
```

Also exclude any other files containing live secrets, user records, or private content.

---

# ⌨️ Command Reference

420VaultBot's primary command prefix is:

```text
420_
```

The following table includes command names represented in the project's command interface.

The live `420_help` panel should be treated as the primary reference for commands available to a particular user.

## General and user commands

| Command | Purpose |
|---|---|
| `420_help` | Open the command directory |
| `420_version` | Display the application version |
| `420_features` | Display feature information |
| `420_auth` | Open authentication controls |
| `420_login` | Account login |
| `420_logout` | Account logout |
| `420_user_manual` | User documentation |
| `420_search` | Search the link library |
| `420_vault_search` | Search the physical Vault |
| `420_drive_search` | Search Google Drive |
| `420_subscription` | Subscription management |
| `420_subscription_signup` | Subscription enrollment |
| `420_subscription_status` | Subscription information |
| `420_server_search` | Search supported server resources |
| `420_status` | Status information |

## Administrator commands

| Command | Purpose |
|---|---|
| `420_admin` | Open the administrative dashboard |
| `420_setup` | Configuration workflow |
| `420_diagnostics` | System diagnostics |
| `420_vault_path` | Configure Vault storage |
| `420_reindex_vault` | Reindex the Vault |
| `420_reloadlinks` | Reload link data |
| `420_showchannels` | View configured channels |
| `420_reindex_drive` | Reindex Drive resources |
| `420_drive_config` | Configure Google Drive |
| `420_drive_sync` | Synchronize Drive metadata |
| `420_drive_status` | Drive synchronization status |
| `420_lockdown` | Apply supported lockdown controls |
| `420_unlock` | Remove supported lockdown state |
| `420_exportserver` | Export supported server information |
| `420_addlicense` | Issue an administrative license |
| `420_revokelicense` | Revoke a license |
| `420_showlicense` | Inspect license information |
| `420_listlicenses` | List licenses |
| `420_approvpayment` | Legacy/payment-approval command where registered |
| `420_resendlicense` | Resend license activation |
| `420_resolvelinks` | Resolve link-library entries |

Some commands require parameters and may be available only in designated channels.

Command names and argument signatures can change between builds. Check the running command directory or the relevant command source for exact syntax.

---

# 🆕 Version 6.4.1 — Reliability and Recovery Update

This release addresses problems discovered during the v6.4.0 source audit.

## Fixed: Discord backup timeout

Previously, the Backup Now button could begin creating a backup before acknowledging the Discord interaction.

When the backup took too long, Discord displayed:

```text
420VaultBot didn't respond in time
```

The backup could still finish on disk despite the failure notification.

### Updated behavior

The backup interaction now acknowledges Discord promptly, performs backup work separately, and sends a completion response.

## Fixed: SQLite backup consistency

The backup workflow now uses SQLite's native backup mechanism for supported database files.

This is safer than copying a database file directly while its write-ahead log may contain uncheckpointed changes.

## Fixed: Backup naming collisions

Backup directories now use more precise timestamps and a random suffix.

This reduces collisions between backups started close together.

## Fixed: Backup verification

The updated backup workflow performs integrity verification before reporting success.

## Fixed: Backup manifest validation

Additional validation restricts unsafe paths in backup manifests and restore targets.

## Fixed: Outdated version labels

Hardcoded version labels in affected Discord interfaces were updated to reflect v6.4.1.

### Testing scope

The release underwent source compilation and focused offline regression testing.

It has **not** been certified through a complete live Discord, payment-provider, Google Drive, and production-database integration test.

---

# 🔒 Security Architecture

420VaultBot contains several security-oriented components.

### Application security features

- HMAC-signed licensing
- Account authentication
- Authenticator-based 2FA
- Administrator access checks
- Subscription entitlement checks
- Terms verification
- Verified payment-webhook processing paths
- Authenticated API requests
- Persistent operational logging
- Backup validation

These features reduce certain risks but are not a substitute for an independent security review.

### Production recommendations

- Keep all credentials out of the repository.
- Rotate exposed tokens immediately.
- Use HTTPS for public endpoints.
- Restrict access to administrative APIs.
- Protect backup archives.
- Regularly test account recovery.
- Keep dependencies updated.
- Monitor payment webhook failures.
- Run only one active production instance against a single-user installation unless concurrency has been explicitly validated.

---

# 🔧 Troubleshooting

## Bot is online but does not respond

An online Discord status does not guarantee that every command or interaction handler is responding.

Potential causes include:

- A blocked event loop
- Slow filesystem operations
- Database contention
- Network delays
- A failed background task
- An expired Discord interaction
- Missing permissions

Check the application logs and diagnostics.

For long-running operations, handlers should acknowledge Discord before performing the expensive work.

## Backup finishes but Discord displays a timeout

Upgrade to v6.4.1 and open a fresh administrative panel.

Test Backup Now again.

Old Discord messages may still contain older interaction views.

## Commands do not work in a particular channel

Check the configured command-channel restrictions.

Normal users and administrators may have different authorized locations.

## Vault search returns no files

Verify the configured storage path, drive availability, read permissions, and indexing status.

## Google Drive search returns no results

Check OAuth credentials, folder permissions, the configured root folder, and metadata synchronization status.

## Audio preview does not work

Confirm the file is supported, the bot can read it, and the preview dependencies are available.

If FFmpeg is required, verify that it can be executed by the bot process.

## Users cannot activate licenses

Check DM availability, licensing records, entitlement state, Terms verification, and expiration information.

## An update reports an older version

Verify that the correct application directory is being launched.

Check for duplicate background instances, service configurations, and old watchdog processes.

---

# 📦 Commercial Source Distribution

420VaultBot can be distributed commercially under a license chosen by its copyright holder.

Purchasers of the source code and subscribers using an installed instance are separate categories.

### Source-code purchasers

Their rights are governed by the commercial software agreement provided with the purchase.

### Community subscribers

Their access is managed through the bot's subscription and licensing system.

A codebase purchaser does not automatically become a subscriber to the seller's Discord community.

Commercial packages should exclude live customer data, private credentials, unauthorized third-party content, and internal operational secrets.

This README is documentation and does not itself grant permission to copy, resell, redistribute, or sublicense the source code.

Refer to the repository's actual `LICENSE` file or commercial agreement for those rights.

---

# ⚠️ Known Limitations and Development Status

420VaultBot is a substantial application, and some areas still require additional hardening.

### In-app update rollback

The in-Discord updater does not yet provide fully transactional rollback of overwritten program files.

Prefer the offline upgrader for production releases.

### Database contention

Some remaining synchronous database operations may delay Discord interactions under load.

### Large backups

Backup operations can consume substantial disk space depending on configured protected directories.

### Third-party services

Payments, Google Drive, and API integrations depend on external credentials, network availability, provider configuration, and service uptime.

### Integration testing

Source-level tests do not guarantee that all commands and controls work correctly in every Discord deployment.

### Hosting

Local Windows hosting can be useful for development and smaller communities, but commercial payment operations benefit from stable infrastructure, persistent storage, monitoring, and reliable webhook delivery.

---

# 🗺️ Development Priorities

Future improvements may include:

- Additional Discord interaction responsiveness fixes
- Transactional application updates
- Expanded database concurrency testing
- Backup storage estimation and retention policies
- Full end-to-end interaction tests
- Improved monitoring and diagnostics
- Additional account and security testing
- Enhanced Vault metadata and discovery
- More comprehensive deployment documentation

These are development priorities rather than promises that the features are already included.

---

# 🤝 Contributions and Support

For bug reports, include:

- 420VaultBot version
- Operating system
- Python version
- Hosting environment
- The command or button involved
- Relevant sanitized logs
- Steps to reproduce the issue

Never include Discord tokens, private API keys, passwords, payment credentials, or sensitive customer records in public issues.

For commercial purchasers, refer to the support arrangements included in the applicable purchase agreement.

---

# ⚖️ Disclaimer

420VaultBot is a software platform for managing Discord communities and digital resources.

Users are responsible for ensuring that any files, plugins, presets, audio samples, archives, software, and external links they distribute are lawful and appropriately licensed.

The application is not affiliated with or endorsed by Discord, Google, Stripe, PayPal, or any other third-party service mentioned in this documentation.

Third-party names and trademarks belong to their respective owners.

---

## 🎛️ 420VaultBot

**One bot. One Vault. One connected music-production ecosystem.**

Built for producers, administrators, and communities that need more than a basic Discord utility.

**Version:** 6.4.1  
**Platform:** Discord / Python  
**Primary interface:** Interactive Discord GUI  
**Command prefix:** `420_`  
**Storage:** Local, external, network, and Google Drive integrations  
**Access:** Licensing, subscriptions, roles, and account authentication  
**Distribution:** Subject to the applicable source-code license
