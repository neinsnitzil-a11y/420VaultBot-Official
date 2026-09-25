# 420Vault Payment Security

420Vault v3 deliberately does **not** store raw card numbers, CVV/CVC, track data, or decryptable card credentials. Those values stay in Stripe/PayPal's PCI payment vault. The bot stores provider-issued opaque customer/subscription/payment identifiers only. This is required even on a trusted local PC because it sharply limits damage if the bot, Discord token, database, backups, or Windows account are compromised.

Secrets belong in `.env` and must never be pasted into Discord. Do not commit `.env`. Use provider-hosted checkout pages. Webhook fulfillment is idempotent and is accepted only after provider signature verification.

The local webhook listener binds to 127.0.0.1 by default. Automatic providers require a stable public HTTPS endpoint forwarding to it. Configure that endpoint with Stripe/PayPal; do not expose the listener without TLS/authentic provider verification.
