# 420VaultBot → Base44 integration instructions

This reference pack originated with the v3.11 API and is carried forward with the current v3.13 source tree. Treat it as the source of truth for the website integration.

## Non-negotiable rules
- Base44 is the UI/control plane; 420VaultBot's SQLite database and services remain authoritative for licenses, entitlements, subscriptions, transactions, TOS, tickets, Vault state, and Discord role/access state.
- Never generate a `420V-...` key in browser code or Base44 data tables. `POST /api/v1/admin/licenses` calls the bot's real `SubscriptionService.admin_grant()` and HMAC license generator.
- Never expose `VAULT_API_KEY` in browser JavaScript. Store it as a Base44 secret and call this API only from Base44 server-side functions.
- Every API request needs `Authorization: Bearer <VAULT_API_KEY>` and `X-Guild-ID`. User routes also need `X-Discord-User-ID` after Base44 has authenticated the Discord account.
- Admin routes additionally verify that `X-Discord-User-ID` is currently a Discord Administrator, configured admin role holder, or Vault Overseer in that guild.
- Do not invent an endpoint. If it is not in `OPENAPI.yaml`, show “Awaiting backend integration” instead of simulating success.
- Payment checkout creation is NOT exposed by the v3.11 website API yet. Stripe/PayPal verified webhook processing remains in the bot. Do not fake checkout success.

## Network
The API and payment webhooks share the aiohttp listener. Set `API_ENABLED=1`. Default host/port are `127.0.0.1:8420`. For Base44, publish it only through an HTTPS reverse proxy/tunnel. Do not expose the raw listener without TLS/access controls.
