# Guided cloud bootstrap contracts

`v1` freezes the safe, provider-neutral boundary used by the Management API
and Flutter guided bootstrap flow. It deliberately excludes every bootstrap
credential value. Provider secrets exist only in the synchronous execute
request model owned by the Management API and are never valid response or
fixture fields.

The contract covers five artifacts:

- `bootstrap-authority-pack.v1`: reviewed provider authority required to
  create and validate the bounded deployment identity;
- `deployment-identity-binding.v1`: an explicit executable identity/auth
  assignment layered over an immutable deployment permission inventory when
  the historical inventory alone is ambiguous;
- `gcp-phase8-api-baseline.v1`: the fixed existing-project API superset owned
  by short-lived GCP bootstrap authority and verified by retained deployment
  credentials;
- `cloud-bootstrap-guide.v1`: safe provider preparation and input metadata;
- `cloud-bootstrap-session.v1`: owner-scoped durable lifecycle state.

The historical manual `/cloud-bootstrap/{provider}/plan` and
`/cloud-bootstrap/import` contracts remain compatible. These contracts add a
guided PoC path; they do not claim formal least privilege or live-cloud proof.
