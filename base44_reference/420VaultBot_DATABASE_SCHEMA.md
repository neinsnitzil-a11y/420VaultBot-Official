# Database schema summary (v11)

Authoritative SQLite tables include:
- `guild_settings`: Discord channel/role IDs, TOS settings, Vault path, feature toggles.
- `licenses`: code, guild, assigned/activated user, status, expiration, activation count, HMAC signature, entitlement.
- `entitlements`: guild/user access source, status, dates, grace, subscription/admin grant linkage.
- `subscription_plans`: price, currency, duration/lifetime, provider configuration, grace.
- `subscriptions`: user/plan/status, billing period, expiration/grace, provider IDs, license.
- `transactions`: provider transaction/event IDs, amount/currency/status.
- `webhook_events`: provider event idempotency/processing state.
- `tos_acceptance`, `tos_attempts`: versioned verification state.
- `support_tickets`, `payment_tickets`: Discord support/payment ticket state.
- `audit_log`: guild/user/action/details.
- `vault_files`, `vault_folders`, `vault_fts`, `vault_scan_state`: physical Vault catalog/search state.
- `link_lists`, `links`, `link_list_members`, `link_fts`, `scrape_jobs`: link library/scraper state.

Schema metadata is version 11. Base44 should not maintain competing authoritative copies of these records.
