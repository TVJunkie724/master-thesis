# Known Limitations

## Evidence limitations

- Offline tests prove contract, calculation, state-machine, redaction,
  packaging, and deterministic provider-adapter behavior—not real deployment.
- Nine Core telemetry cases, three local command cases, and separate AWS/Azure
  Event-to-L4 and graphical L3-to-L5 cuts have supervised evidence. These are
  not nine complete-profile application passes. The normal application
  deploy/reconnect/simulator-to-L5 workflow remains unverified.
- Estimated costs use frozen snapshots and assumptions; they are not invoices
  or a FinOps reconciliation.

## Scope limitations

- one standalone Six-layer architecture and one cost objective;
- one single-user/single-node PoC runtime;
- pre-existing deployment administrator credentials;
- the shared Terraform root requires Azure authentication even for an AWS-only
  plan; the approved PoC retains this dependency through an explicit local
  Deployer secret-file opt-in, without adding Azure resources. This is not
  provider-independent deployment or production multi-tenancy;
- bounded confirmed preparation, not general account administration;
- provider preflight and bounded preparation/repair are represented in Flutter,
  but remain offline contract evidence until supervised provider evaluation;
- typed Twin interchange and bounded user functions, not arbitrary projects;
- immutable deployed definitions, no update/migration/rollback;
- access links and one telemetry roundtrip, no dashboard administration;
- three provider-local plus six directed Small **Core** scenarios, not every
  layer permutation; GCP L4/L5 are excluded from complete-profile evaluation.

## Security and operational limitations

Production authentication/RBAC, multi-tenancy, credential lifecycle,
least-privilege generation, HA databases, backups, distributed locks, disaster
recovery, signed desktop distribution, and support operations are outside
scope.

Provider prerequisites such as billing, quotas, organization policies,
tenant-wide consent, Marketplace/legal acceptance, and some interactive access
setup may require manual operator action even when administrator credentials
are valid.

These limits belong in result interpretation and threats to validity. They are
not hidden future delivery promises.
