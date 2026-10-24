# 420VaultBot v6.4.3 — Public Profile Discovery

Added `420_profile_search [query]` and a **Find Public Profiles** button in the paginated `420_help` directory. Search names, usernames, producer names, DAWs and genres. Results are paginated and can open existing public profile cards.

Privacy: only explicitly opted-in profiles in the current guild are queried; accounts, emails, licenses and 2FA status are never included in search output. Private changes are rechecked on selection. Existing profile editing and public/private toggle remain unchanged.

Upgrade from v6.4.2: stop the bot, back up the complete current installation, then replace application code with this release using your supported upgrade mechanism. Preserve .env, databases, licenses, accounts, and runtime data. Restart and use `420_profile_search` or `420_help`.

Release tests are offline; confirm real Discord interaction behavior before deploying commercially.
