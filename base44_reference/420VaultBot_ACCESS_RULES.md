# Access rules

| State | TOS required when enabled | Paid entitlement required | Bot admin |
|---|---:|---:|---:|
| Ordinary user | Yes | Yes | No |
| Beta Tester | Yes | No | No |
| Vault Overseer | Yes for normal access | No | Yes |
| Discord Administrator/configured bot admin | Yes for normal access | No | Yes |

A paid ordinary user still needs license activation. The license row is considered activated when its `user_id` is bound to the member and the license is active for the entitlement.

Admin API routes are stricter than service authentication alone: they require the shared API secret plus the acting Discord user's current admin/Vault Overseer authorization.
