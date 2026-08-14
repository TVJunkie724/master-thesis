# Deployment access contract

`deployment-access.v1` is the canonical, owner-scoped, secret-free read model
for the two interactive surfaces of a deployed Twin2MultiCloud PoC:

- L4 semantic twin inspection;
- L5 raw and rollup visualization.

An available snapshot contains exactly one L4 and one L5 surface. Its internal
evidence is valid for `five-layer-baseline@2` and for the inheriting
`six-layer-eventing@1` profile. Historical `five-layer-baseline@1` deployments
use the explicit unsupported form instead of fabricated links. The contract is
closed at every object boundary and does not accept Terraform output
containers, provider credentials, datasource keys, tokens, certificates, or
passwords.

`deployment-access-credential.v1` is intentionally separate. It is valid only
for the explicit GCP Grafana Viewer rotation operation and is returned once.
It must never be persisted or logged.

The nine valid placement fixtures cover every independent L4/L5 provider pair;
L3 Hot follows L5 by the frozen Five-layer v2 co-location invariant. The
fixture URLs are reserved documentation examples, not live endpoints.

Synchronize generated consumer copies with:

```bash
python scripts/sync_deployment_access_contracts.py
python scripts/sync_deployment_access_contracts.py --check
```
