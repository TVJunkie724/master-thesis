# Dashboard And Twins

The dashboard is the operational entrypoint. It summarizes twin state and pricing
health, then lists the user's active twins. Pricing readiness appears here because it
is an account/provider concern rather than a field inside one twin.

## Twin Actions

- create a new draft twin;
- open an existing twin overview;
- edit configuration when lifecycle rules permit;
- soft-delete a twin after confirmation;
- open the global Pricing Review workspace.

Twin names are unique per user among active twins. Deletion changes state to
`inactive`; it does not erase deployment history opportunistically.

## State Meaning

| State | User meaning |
|---|---|
| `draft` | configuration is incomplete or was invalidated by edits |
| `configured` | required configuration is valid and deployment can be prepared |
| `deploying` | one deployment operation is active |
| `deployed` | latest deploy completed successfully |
| `destroying` | one destroy operation is active |
| `destroyed` | infrastructure was torn down successfully |
| `error` | latest operation failed; inspect history before retry |
| `inactive` | soft-deleted and absent from the normal dashboard |

The twin overview is the read/operate surface: configuration summary, selected
architecture, readiness, deployment actions, operation history, logs, outputs,
verification, and developer/test utilities when explicitly enabled.
