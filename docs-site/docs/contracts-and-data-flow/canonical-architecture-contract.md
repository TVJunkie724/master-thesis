# Canonical Architecture Contract

The cross-service runtime has one standalone contract:
`six-layer-eventing@1`. It fixes the logical responsibilities, components,
ports, edges, provider bundles, component catalog, workload, cost bindings,
deployment specification, and Manifest v4 boundary.

Despite historical internal schema names, this is not a runtime profile
framework. The Management API offers only:

- a read-only canonical contract;
- an automatically created digest pin for each Twin; and
- immutable resolved-architecture reads for calculation evidence.

There is no catalog, registration, inheritance, selection, change preview, or
client-authored topology.

## Resolution flow

1. Management injects the canonical pin, exact workload and extension bindings
   into an internal calculation request.
2. Optimizer admits only complete Six-layer provider assignments and emits
   matching resolved architecture/deployment-specification documents.
3. Management validates all identities, digests, costs, references, and graph
   cross-links before committing them atomically.
4. Deployer derives packages, readiness requirements and Terraform inputs from
   that immutable graph.
5. Flutter renders only Management-owned contract/evidence reads.

Canonical sources live under `contracts/architecture-profiles/`; generated
service copies are drift-gated. Five-layer v1 remains an isolated Optimizer
comparison baseline and is not part of this contract bundle.
