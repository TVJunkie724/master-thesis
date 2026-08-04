# Guided cloud bootstrap contracts

`v1` freezes the safe, provider-neutral boundary used by the Management API
and Flutter guided bootstrap flow. It deliberately excludes every bootstrap
credential value. Provider secrets exist only in the synchronous execute
request model owned by the Management API and are never valid response or
fixture fields.

The contract covers three artifacts:

- `bootstrap-authority-pack.v1`: reviewed provider authority required to
  create and validate the bounded deployment identity;
- `cloud-bootstrap-guide.v1`: safe provider preparation and input metadata;
- `cloud-bootstrap-session.v1`: owner-scoped durable lifecycle state.

The historical manual `/cloud-bootstrap/{provider}/plan` and
`/cloud-bootstrap/import` contracts remain compatible. These contracts add a
guided PoC path; they do not claim formal least privilege or live-cloud proof.
