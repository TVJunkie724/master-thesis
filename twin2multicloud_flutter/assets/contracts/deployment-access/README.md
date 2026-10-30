# Deployment access contract

`deployment-access.v1` is the canonical, owner-scoped, secret-free read model
for the two bounded inspection surfaces of a deployed Twin2MultiCloud PoC:

- L4 semantic twin inspection;
- L5 authenticated raw and rollup readback.

An available snapshot contains exactly one L4 and one L5 surface. Its internal
evidence is valid only for `six-layer-eventing@1`. The explicit unsupported
form remains available for records without compatible access evidence. The
contract is closed at every object boundary and does not accept Terraform output
containers, provider credentials, datasource keys, tokens, certificates, or
passwords.

L5 reuses the approved deployment principals: AWS SigV4, an Azure Function key
resolved only during verification, and a GCP identity token. No dashboard
account or additional user-facing credential is created or persisted.

The nine valid placement fixtures cover every independent L4/L5 provider pair.
The fixture URLs are reserved documentation examples, not live endpoints.

Synchronize generated consumer copies with:

```bash
python scripts/sync_deployment_access_contracts.py
python scripts/sync_deployment_access_contracts.py --check
```
