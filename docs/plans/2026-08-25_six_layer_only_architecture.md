---
title: "Six-layer-only Thesis Architecture"
description: "Removal plan for the intermediate Five-layer v2 runtime and the cross-service Five-layer v1 compatibility surface."
tags: [architecture, thesis-scope, six-layer, cleanup]
lastUpdated: "2026-08-25"
version: "1.0"
---

# Six-layer-only Thesis Architecture

## Decision

`six-layer-eventing@1` is the only architecture profile exposed by the
Management API, Flutter, and the Deployer. It owns its complete L1-L6 contract,
workload, cost model, provider mappings, deployment specification, runtime
artifacts, and verification evidence.

The intermediate `five-layer-baseline@2` implementation is removed. Six-layer
must not inherit its profile, catalog, workload, implementation commits,
runtime paths, Terraform names, Python types, or generated fixtures.

The original Five-layer approach remains only inside `2-twin2clouds` as a
historical optimizer baseline. It is not a selectable architecture profile and
has no Management API, Flutter, Deployer, Terraform, or shared-contract surface.

## Retention Matrix

| Capability | Historical Five-layer optimizer | Six-layer runtime |
|---|---:|---:|
| Cost-baseline calculation | retained | retained |
| Shared architecture profile | removed | canonical |
| New Twin selection | removed | canonical |
| Deployment | removed | canonical |
| Runtime artifacts and Terraform | removed | canonical |
| Live E2E target | excluded | sole target |

## Migration Rules

1. Replace Five-layer-v2-named shared code with Six-layer-owned code only when
   the behavior is required by the Six-layer runtime.
2. Delete the standalone Five-layer-v2 optimizer, profile, provider mappings,
   fixtures, deployment path, UI assets, and evaluation output.
3. Delete cross-service Five-layer-v1 compatibility. Git history remains the
   archive; the active tree does not carry read/deploy/destroy support for it.
4. Preserve generic contract schema versions such as RTA v2, RDS v2, and
   Deployment Manifest v4. Their version is independent of the removed
   Five-layer profile version.
5. Default verification remains offline and must not create cloud resources.

## Completion Criteria

- No production path accepts `five-layer-baseline@1` or
  `five-layer-baseline@2`.
- No Five-layer-v2 module, class, contract, runtime directory, Terraform file,
  Flutter asset, or generated fixture remains.
- Six-layer contracts validate without an inherited-profile reference.
- Safe Optimizer, Management API, Deployer, Flutter, contract, and docs gates
  pass without live E2E execution.
