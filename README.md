# 🌿 420VaultBot v5.8.2

> **Premium Discord vault, licensing, subscription, search, delivery, and producer-resource management platform.**

420VaultBot is a full Discord-based distribution and management system designed for music-production communities, private vaults, producer services, and premium resource libraries. Version **5.8.2** brings the Vault, licensing, subscriptions, Terms onboarding, payments, link search, local/external storage, Google Drive integration, administrative tools, and user-facing search experiences together under one system.

Instead of forcing administrators to manage a collection of unrelated scripts, commands, spreadsheets, payment notes, and download channels, 420VaultBot provides a centralized workflow built around Discord and its companion Admin GUI.

---

## 📌 Version

**Current Release:** `v5.8.2`

**Release Family:** `5.x`

**Recommended Python:** `Python 3.12`

**Primary Platform:** Windows

**Storage:** Local drives, external drives, network-accessible paths, Google Drive, and indexed link lists

---

## ✨ What Is 420VaultBot?

420VaultBot is built for communities that distribute and organize digital music-production resources such as:

- 🥁 Drum kits and drum sounds
- 🎹 Presets and preset banks
- 🎼 MIDI files
- 🔊 WAV, MP3, and AIFF audio
- 🎛️ Plugin-related resources
- 🎚️ Expansion banks
- 🎹 Omnisphere banks
- 🧪 Serum banks
- 🎹 Zenology banks
- 🌌 Portal banks
- 🔁 Loops
- 💥 FX and one-shots
- 🎵 Gross Beat presets
- 📦 ZIP/RAR archives
- 🎚️ FL Studio projects (`.flp`)
- 📁 Complete folders and collections
- 🔗 Indexed external resource links

The bot is designed around a simple idea: **search the collection instead of digging through it manually.**

---

# 🚀 Major v5.8.2 Features

## 🔎 Unified Search Experience

420VaultBot provides search interfaces for large collections without requiring users to manually browse thousands of files or links.

The system can work with multiple resource sources, including:

- Physical Vault storage
- External drives
- Network-accessible storage
- Google Drive
- Imported link lists
- Scraped resource lists

Search results can be paginated so large result sets remain usable inside Discord.

Where supported, result interfaces can provide navigation controls and direct resource actions instead of dumping enormous walls of text into a channel.

---

## 💾 Physical Vault System

The Vault is one of the core components of 420VaultBot.

Administrators are **not required to name a drive or folder `420Vault`**. The Vault root is configurable and may point to locations such as:

```text
E:\Producer Vault
D:\420Vault
F:\Sound Libraries
\\SERVER\MusicVault
```

This makes the system suitable for internal drives, USB drives, large external HDD/SSD storage, and compatible network paths.

### Persistent Indexing

The bot does not need to walk the entire storage drive every time somebody performs a search.

Vault metadata is indexed into a persistent database so searches can be performed quickly after the initial indexing process.

The indexing system is designed to recognize individual files and resources stored inside the configured Vault structure.

### Supported Resource Types

Typical indexed resources include:

```text
.wav
.mp3
.aiff
.aif
.mid
.midi
.flp
.zip
.rar
.7z
```

Additional preset, bank, project, archive, and music-production formats can also be included by the Vault configuration/indexing implementation.

### Folder Delivery

Entire folders can be treated as resources.

When folder delivery is requested, the system can package the folder into an archive before attempting delivery.

The archive is size-checked before Discord upload. If it exceeds the upload capacity available for the current Discord environment, the bot can provide an appropriate fallback instead of blindly attempting an upload that will fail.

---

# 🎧 Audio Preview Support

Audio resources should not behave like ordinary archives.

Supported audio files such as WAV and MP3 resources can be presented so users can preview playable audio directly through Discord where Discord supports the format.

This is particularly useful for:

- One-shots
- Loops
- Drum samples
- FX
- Melody samples
- Preview tracks

Users can hear the resource before deciding whether they want to download it.

---

# ☁️ Google Drive Integration

420VaultBot can use Google Drive as an additional Vault source rather than relying on one hard-coded Drive link.

The administrator can configure a Drive location and use the integration to index/search resources stored remotely.

This is especially useful for very large libraries where storing every resource on the machine running the bot is impractical.

### Google Drive Features

The v5.8.2 architecture supports the workflow for:

- Configurable Drive location
- Connection testing
- Metadata synchronization/indexing
- Large Drive collections
- Searchable Drive metadata
- Paginated results
- Drive resource discovery
- Integration with the Vault search experience

A Drive configuration can be managed independently instead of requiring every unrelated Admin GUI field to be completed first.

> Large Drive libraries can take time to perform their initial metadata synchronization. Subsequent searches should rely on indexed metadata instead of rebuilding the entire remote inventory for every query.

---

# 🔗 Link Database & Resource Lists

420VaultBot can also search large text-based resource databases.

This allows administrators to maintain large link collections independently from physical Vault storage.

The system is designed for collections containing tens of thousands of links.

### Link Management

Administrators can:

- Import link lists
- Add additional lists later
- Preserve existing links when adding new data
- Deduplicate indexed resources
- Reload link data
- Re-index updated collections
- Search existing resource lists
- Add scraper-generated results

New resources can therefore be added without rebuilding the collection manually.

---

# 🕷️ Scraper Integration

The administrative workflow can incorporate resource scraping/import tools for building or extending searchable link collections.

After a scrape, the administrator can choose whether the resulting links should:

1. Create a new resource list, or
2. Be appended to an existing list without overwriting its existing entries.

After import, the relevant search index can be refreshed so the newly discovered resources become searchable.

---

# 🔐 Premium License System

420VaultBot uses a gated license system rather than exposing all premium functionality immediately after a user joins.

Typical license keys use the compact format:

```text
420V-XXXX-XXXX-XXXX
```

The license system is designed to associate access with the intended Discord user and license record.

## License Delivery

License activation is designed around Discord UI instead of requiring users to memorize a dedicated activation command.

When a license is issued, the user can receive a private DM containing information such as:

- License key
- License tier
- Expiration
- Subscription information
- Activation controls

The configured License channel can also contain the persistent license-entry interface used by the server.

### Manual Administrative Licenses

Administrators can grant licenses manually when necessary.

A manually granted license can bypass the normal paid-subscription requirement, making it useful for staff, promotions, testing, partnerships, or individually approved access.

---

# 💳 Subscription System

420VaultBot v5.8.2 is designed as a premium platform and supports configurable subscription access.

A premium default pricing structure can use:

| Term | Default Price |
|---|---:|
| 1 Month | $25 |
| 3 Months | $75 |
| 7 Months | $100 |
| 1 Year | $150 |
| 2 Years | $200 |
| 3 Years | $250 |
| Lifetime | $500 |

These values can be treated as defaults rather than permanently hard-coded business rules. Administrators should be able to adjust available tiers and pricing through configuration.

### Subscription Lifecycle

The access workflow can include:

- Purchase selection
- Payment processing/approval
- License generation
- User activation
- Subscription expiration tracking
- Renewal reminders
- Grace/expiration handling
- Role removal when access expires
- Renewal workflow

Users approaching expiration can receive advance renewal notifications, including a warning approximately seven days before expiration where configured.

---

# 💰 Payment Workflows

420VaultBot is designed to support both automated providers and manually approved payment methods.

Potential provider workflows include:

- Stripe
- PayPal
- Cash App/manual verification
- Additional configurable providers

Cash App is treated as a manual payment workflow rather than pretending it provides a general-purpose public subscription API.

Payment flows can create tickets for review when administrator action is required.

### Payment Safety

Sensitive payment-card information should **never** be collected or stored directly by 420VaultBot.

Card processing should be delegated to established payment providers. Provider credentials and secrets should be handled securely and should not be displayed unnecessarily in logs or Discord messages.

### Idempotent Approval

Payment approval logic should prevent the same successful payment from accidentally generating multiple licenses or granting duplicate subscription periods.

---

# 🎟️ Ticket System

420VaultBot includes ticket-oriented workflows for support and administrative review.

Tickets can cover areas such as:

- Payment approval
- Subscription issues
- Bot crashes
- Bug reports
- Vault requests
- Resource requests
- General bot support

A dedicated `Tickets` channel/category can be configured for administrative handling.

---

# 📜 Terms of Service Onboarding

420VaultBot can gate server access behind a Terms of Service onboarding workflow.

New members can be directed to the Terms area before receiving normal access.

The Terms system can include:

- Terms acceptance
- Terms version tracking
- Reading-verification quiz
- Configurable passing percentage
- Verified role assignment
- Re-verification after Terms updates
- Persistent Terms panel
- Administrative bypass

The configurable passing percentage must remain within a valid `1–100` range.

When the Terms version changes, previously verified members can be required to accept the updated Terms again depending on administrator configuration.

> Server moderation actions should comply with Discord's platform capabilities and policies. Network-level/IP banning is not a standard Discord bot capability and should not be represented as one.

---

# 👥 Roles

The bot's access model can use dedicated Discord roles.

### `Verified`

Assigned after the configured Terms onboarding requirements have been completed.

### `Subscribed`

Represents active paid access where the subscription system is enabled.

### `Beta Tester`

Can provide approved testers with access without requiring a normal paid subscription.

### `Vault Overseer`

Administrative bot role with elevated access to VaultBot management functionality.

### Administrators

Discord administrators and specifically authorized bot administrators can bypass user-facing restrictions where appropriate.

---

# 🔒 Access Control

420VaultBot separates ordinary user functionality from administrative functionality.

User commands should remain unavailable until the required verification/license/access state has been satisfied.

The system should evaluate a canonical access state rather than implementing contradictory access checks throughout unrelated commands.

This helps ensure that subscription users, manually licensed users, Beta Testers, and administrators receive the access intended by configuration.

---

# 💬 Command Style

420VaultBot uses the recognizable `420_` command naming convention for its text-command workflow.

Examples of administrative and legacy-compatible command names include:

```text
420_search
420_searchkit
420_sendlink
420_vault_search
420_addlicense
420_reindex_vault
420_reloadlinks
420_resolvelinks
420_listlicenses
420_resetuserlicenses
420_revokelicense
420_showchannels
420_showlicense
420_download_vault
420_admin_delete_vault_index
```

Exact availability depends on the v5.8.2 configuration and the user's permissions.

The license activation experience itself is intended to use the dedicated activation UI rather than requiring a `420_activatelicense` command.

---

# 🖥️ Admin GUI

A major goal of 420VaultBot is to avoid requiring the owner to edit Python source code every time a server setting changes.

The Admin GUI acts as the central configuration interface.

Administrative configuration can include:

- Discord bot settings
- Bot token configuration
- Guild/server configuration
- Channel configuration
- Role configuration
- Vault root path
- Vault indexing
- Link-list management
- Scraper/import controls
- Google Drive configuration
- Connection testing
- Payment providers
- Provider credentials
- Subscription tiers
- Pricing
- License settings
- Terms configuration
- Ticket configuration
- Logging configuration

Sensitive secrets should be stored and handled appropriately rather than being printed in plaintext throughout the interface or logs.

---

# 📂 Recommended Project Layout

A v5.8.2 installation may resemble:

```text
420VaultBot-v5.8.2/
│
├── bot/
├── admin/
├── database/
├── vault/
├── indexes/
├── linklists/
├── scraper/
├── payments/
├── tickets/
├── logs/
├── config/
├── data/
│
├── README.md
├── requirements.txt
├── install.bat
└── ...
```

The exact source layout may differ between builds. Do not move internal application files unless the build documentation specifically instructs you to do so.

---

# ⚙️ Installation

## 1. Install Python 3.12

420VaultBot is intended to run with Python 3.12 for the supported build environment.

Check your installation:

```powershell
py -3.12 --version
```

or:

```powershell
python --version
```

If Windows reports:

```text
No suitable Python runtime found
```

then Python 3.12 is not currently available through the Python launcher and must be installed before using commands that explicitly target `py -3.12`.

---

## 2. Extract the Release

Extract the entire release into its own directory.

Example:

```text
C:\Users\YourName\Downloads\420VaultBot-v5.8.2
```

Do not run individual files directly from inside the ZIP archive.

---

## 3. Run the Installer

If your build includes `install.bat`, launch it from the extracted project directory.

If the window immediately closes, open PowerShell inside the project directory and run:

```powershell
.\install.bat
```

This keeps errors visible instead of closing the terminal before they can be read.

---

## 4. Manual Dependency Installation

If required:

```powershell
py -3.12 -m pip install --upgrade pip
py -3.12 -m pip install -r requirements.txt
```

Using the explicit Python version prevents dependencies from accidentally being installed into a different Python installation.

---

# 🤖 Discord Bot Setup

The bot owner must create/configure the Discord application used by the installation and provide the required credentials to the local configuration.

The bot must have the permissions required for the features the administrator enables, which can include:

- Viewing configured channels
- Sending messages
- Embedding links
- Attaching files
- Reading message history
- Managing applicable roles
- Creating/managing ticket channels where enabled
- Sending DMs to users who permit them

Do not grant permissions the bot does not require.

---

# 🏗️ Initial Configuration

After installation, launch the Admin GUI and configure the environment before opening the system to users.

A typical setup order is:

1. Configure the Discord bot/token and server.
2. Configure administrator/Vault Overseer access.
3. Configure required roles.
4. Configure License, Logs, and Tickets destinations.
5. Configure Terms onboarding if enabled.
6. Select the physical Vault root.
7. Build the initial Vault index.
8. Import link lists.
9. Configure Google Drive if used.
10. Configure subscription tiers and payment providers.
11. Test connections.
12. Verify license activation with a test account.
13. Test Vault search and delivery.
14. Test expiration/role behavior before production use.

---

# 📁 Configuring the Vault

In the Admin GUI, choose the root folder containing the resources you want indexed.

For example:

```text
E:\420 Producer Vault
```

The drive letter does not matter. If Windows assigns the external drive another letter, update the Vault configuration to the correct path.

After selecting the path, run the Vault indexing process.

For large libraries, the first scan can take significantly longer than normal searches because the bot must discover and store metadata for the collection.

Once complete, normal searches should query the persistent index.

---

# 🔄 Re-indexing

Re-index when resources have been added, removed, renamed, or reorganized.

Depending on the build, this can be initiated through the Admin GUI or the appropriate administrator command such as:

```text
420_reindex_vault
```

Indexing should not be triggered for every ordinary user search.

---

# 🔍 User Workflow

Once a member has completed the required Terms/license/subscription flow, the normal experience is straightforward.

A user can open or invoke the appropriate search experience and search for a resource such as:

```text
808
Omnisphere
Serum
Analog Lab
Pierre Bourne
Trap MIDI
Guitar Loop
Kick
Portal
```

The bot searches the applicable indexes and returns matching resources.

Large result sets can be navigated using pagination rather than being truncated into one enormous message.

---

# 📥 Resource Delivery

Delivery behavior depends on the resource type and source.

### Small physical files

The bot can upload files directly when they fit within Discord's currently available upload limit.

### Audio

Compatible audio can be delivered in a form that permits Discord playback/preview where supported.

### Folders

Folders can be archived, checked, and then uploaded if the resulting archive fits the available limit.

### Oversized resources

Resources that exceed Discord's current upload capacity should use the configured fallback rather than failing silently.

### Links

Link-database resources can be returned as the appropriate external resource link.

### Google Drive

Drive-backed resources can be resolved through the configured Google Drive workflow.

---

# 📝 Logging

Operational logging is important for diagnosing a production bot.

The configured logging system should capture meaningful events such as:

- Startup/shutdown
- Connection failures
- Index operations
- License actions
- Subscription actions
- Payment processing state
- Ticket activity
- Delivery errors
- Search/index failures
- Administrative actions

A configured Discord `Logs` channel can receive appropriate administrative events, while detailed local logs can be retained for technical diagnosis.

Secrets, complete payment credentials, and other sensitive values should never be dumped into public logs.

---

# 🛡️ Security Recommendations

Anyone operating a 420VaultBot deployment should follow standard secret-management practices.

**Never commit the following to a public GitHub repository:**

```text
Discord bot tokens
Stripe secret keys
PayPal secrets
OAuth client secrets
Webhook secrets
Database passwords
Encryption keys
License-signing secrets
Private API credentials
```

If a credential is accidentally published, removing it from the latest commit is not sufficient. Revoke/rotate the exposed credential immediately.

Use environment variables, protected configuration, or another appropriate secrets-storage mechanism for production deployments.

---

# 🧪 Before Going Live

Test the installation with a private test account before inviting customers.

Verify at minimum:

- Terms acceptance works
- Verified role is granted correctly
- License DM is delivered
- License activation works
- Duplicate activation is handled correctly
- Subscription access is granted correctly
- Beta Tester bypass behaves correctly
- Manual license bypass behaves correctly
- Search pagination works
- Vault results are accurate
- Link results do not contain unwanted duplicates
- Audio preview works
- Folder archiving works
- Oversized file fallback works
- Google Drive search works
- Tickets are created in the correct location
- Logs appear in the correct location
- Expired users lose only the access they are supposed to lose
- Renewal restores access correctly

Never test payment or expiration logic for the first time against a large production user base.

---

# 🧰 Troubleshooting

## `py -3.12` is not found

Run:

```powershell
py --list
```

If Python 3.12 is absent, install Python 3.12 before continuing.

---

## `install.bat` opens and closes

Open PowerShell in the project folder and run:

```powershell
.\install.bat
```

The error will remain visible in the terminal.

---

## Bot is online but commands do not work

Check:

- Bot token
- Guild/server configuration
- Command prefix/configuration
- Required Discord intents
- Channel permissions
- Role permissions
- License/access state
- Terms verification state
- Admin/Vault Overseer configuration

---

## Vault search returns nothing

Confirm that:

1. The Vault root still exists.
2. The external drive is connected.
3. The configured drive letter/path is correct.
4. The Vault has been indexed.
5. The database/index exists.
6. A re-index has been performed after major storage changes.

---

## External drive changed letters

Windows may assign a removable drive a different drive letter.

Update the Vault root in the Admin GUI and revalidate/re-index the storage as necessary.

---

## Google Drive says connected but resources are missing

Check that the configured Drive root is the location that actually contains the Vault data and that metadata synchronization/indexing has completed.

For very large collections, initial synchronization may require substantial time.

---

## WAV files download instead of previewing

Verify that the delivery code is sending the audio using a Discord-supported attachment type and is not unnecessarily wrapping individual previewable audio files in an archive.

Folder/archive downloads and individual audio previews should be handled differently.

---

# 🔁 Updating from an Older Release

Before replacing an existing installation:

1. Stop the bot.
2. Back up the database.
3. Back up configuration files.
4. Back up license/subscription records.
5. Back up custom link lists.
6. Back up any local metadata/indexes that the migration instructions identify as reusable.
7. Extract v5.8.2 into its own versioned directory.
8. Apply required configuration migration.
9. Install/update dependencies.
10. Start the bot in a private/test environment first.

Do **not** blindly overwrite a working production installation without a backup.

A recommended versioned layout is:

```text
420VaultBot/
├── backups/
├── releases/
│   ├── v5.8.1/
│   └── v5.8.2/
└── shared-data/
```

This makes rollback significantly easier if a release-specific problem is discovered.

---

# 🆕 v5.8.2 Release Focus

Version **5.8.2** represents the current 420VaultBot 5.x production direction, centered around:

- Premium subscription-oriented deployment
- Configurable Vault locations
- Persistent Vault indexing
- Physical resource delivery
- Audio preview workflows
- Large link-list support
- Deduplication
- Search pagination
- Google Drive Vault integration
- License DM/GUI activation
- Removal of the dedicated activation-command dependency
- Configurable subscription periods
- Payment-provider workflows
- Manual payment approval support
- Ticket integration
- Terms onboarding
- Verified/Subscribed/Beta Tester/Vault Overseer access models
- Administrative configuration through the GUI
- Scraper/import integration
- Safer secret handling
- Improved production deployment workflow

---

# 🧭 Administrator vs. User Responsibilities

### Administrator

The server owner/operator is responsible for configuration, storage availability, indexes, payment-provider accounts, pricing, server permissions, resource rights, backups, and support.

### User

Users interact primarily with the Discord-facing system: completing onboarding, activating authorized access, searching resources, navigating results, previewing supported audio, and retrieving resources they are permitted to access.

---

# ⚖️ Responsible Use

420VaultBot is a management and delivery platform. The software does not grant rights to redistribute third-party content.

Operators are responsible for ensuring that resources made available through their deployment are distributed in accordance with applicable licenses, agreements, intellectual-property rights, laws, Discord policies, payment-provider requirements, and any other obligations applicable to their operation.

Do not use the project to distribute content you are not authorized to distribute.

---

# 📦 Selling or Deploying the Codebase

A purchaser/operator of a 420VaultBot deployment should receive the documentation and configuration information required to operate their own installation without needing access to the original developer's private credentials.

Before transferring a deployment:

- Remove personal API credentials.
- Remove private Discord tokens.
- Remove live payment secrets.
- Remove private signing/encryption secrets that should not transfer.
- Provide clean configuration placeholders.
- Include installation instructions.
- Explain the Admin GUI.
- Explain backup/restore procedures.
- Explain subscription configuration.
- Explain Vault indexing.
- Explain Google Drive configuration if included.
- Explain which credentials the new operator must create themselves.

Never ship your personal production credentials inside a distributable release.

---

# 🌿 420VaultBot

**Search it. Preview it. Deliver it. Manage it.**

420VaultBot v5.8.2 is built to turn a large producer-resource collection into an organized premium Discord platform instead of a maze of folders, download channels, disconnected links, and manual access management.

---

## Version Information

```text
Product: 420VaultBot
Version: 5.8.2
Release Line: 5.x
Recommended Runtime: Python 3.12
Interface: Discord + Admin GUI
Vault Index: Persistent local database
Storage: Configurable local/external/network storage + Google Drive
Access: License / Subscription / Role based
```

---

**© 420VaultBot. All applicable rights reserved.**

> See the license distributed with the codebase for the exact rights, restrictions, redistribution terms, and commercial-use conditions that apply to your copy.
