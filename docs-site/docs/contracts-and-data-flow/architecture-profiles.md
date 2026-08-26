# Architecture Profile Contracts

The cross-service runtime exposes one reviewed profile:
`six-layer-eventing@1`. It is a standalone contract covering logical
responsibilities, provider implementations, component catalog, workload,
costing, resolved architecture, deployment specification, and Manifest v4.

Five-layer v1 remains an immutable historical calculation in the Optimizer. It
is not published through the shared profile catalog and is not selectable in
Management, Deployer, Terraform, or Flutter.

## Records and ownership

| Record | Owner | Boundary |
|---|---|---|
| `ArchitectureProfile` | repository contracts | six logical responsibilities, components, ports, edges, optimization slots, completeness rules |
| `ProviderImplementationProfile` | repository contracts | one provider's capability claims and logical-to-catalog mapping |
| `DeploymentComponentCatalog` | repository contracts | packages, runtimes, pricing/formula references, and Terraform bindings |
| `ResolvedTwinArchitecture` | Optimizer | immutable winning assignments, edges, evidence, cost, and pinned references |
| `ResolvedDeploymentSpecification` | Optimizer | exact provider-specific dimensions required by deployment |
| `DeploymentManifest v4` | Management | profile-matched operation package sent to Deployer |

Clients select only the reviewed Six-layer ID and version. They cannot author
components, edges, provider mappings, services, evidence, digests, or Terraform
values.

## Resolution flow

1. Management resolves the selected profile and immutable workload references.
2. Optimizer admits only complete Six-layer candidates and emits a matched RTA
   v2/RDS v2 pair.
3. Management validates all run, profile, pricing, deployment, cost, and digest
   cross-links before committing the result atomically.
4. Management packages the exact evidence in Manifest v4.
5. Deployer validates the pinned profile/catalog graph and derives packages and
   Terraform inputs without inferring a compatibility profile.
6. Flutter renders the Management-owned selection and resolved architecture.

`ARCHITECTURE_PROFILE_RESOLUTION_ENABLED=false` is a fail-closed operational
rollback. An enabled failure never falls back to a legacy deployment result.
Offline evidence does not imply that supervised live-capacity gates passed.

## Contract synchronization

The canonical source is `contracts/architecture-profiles/`. Generated service
copies and Flutter demo assets are synchronized with:

```bash
python scripts/refresh_six_layer_contract_digests.py
python scripts/sync_six_layer_contracts.py --sync --check
```

The sync gate rejects intermediate-profile identities, inherited manifest
fields, digest drift, schema failures, incomplete provider mappings, and stale
RTA/RDS/Manifest fixtures.

See [Architecture Contract Development](../developer-guide/architecture-profile-contracts.md)
for extension rules.
