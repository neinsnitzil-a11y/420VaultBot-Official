# Payment flow

Existing bot payment lifecycle:
1. A plan/provider flow creates a pending transaction/subscription.
2. Stripe/PayPal hosted provider handles payment. Cash App/manual remains manual approval.
3. Provider webhook is verified server-side.
4. Webhook event IDs are reserved/deduplicated in `webhook_events`.
5. Successful fulfillment creates/updates subscription + entitlement + real HMAC-backed license.
6. Bot can DM the assigned user the activation button.
7. Failed renewal enters `past_due`; grace is anchored to the billing-period boundary rather than repeatedly extended.
8. Expiry revokes/expirs the subscription, entitlement and license according to service logic.

Base44 v3.11 integration limitation: there is no website checkout-creation endpoint in `OPENAPI.yaml` yet. The website must not claim checkout is wired until that endpoint is implemented.
