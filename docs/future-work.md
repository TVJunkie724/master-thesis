# Future research extensions

This document records conceptual extensions that are deliberately outside the
Twin2MultiCloud thesis PoC. It is neither a product roadmap nor a commitment to
implement them.

## Optimization objectives

The retained internal cost-scoring strategy is a valid boundary for later
latency, sustainability, resilience or policy objectives. A future study would
need to define comparable metrics, measurement provenance, normalization,
trade-off semantics and an evaluation design before exposing another strategy.
Disabled runtime objectives or weighted scoring would not constitute evidence
of that capability.

## Alternative architecture contracts

The PoC has one standalone `six-layer-eventing@1` contract. Comparing alternative
Digital Twin decompositions could become a separate experiment with independently
versioned contracts, admissibility rules and evaluation matrices. It should not
be implemented as inheritance from the current architecture or as an unvalidated
profile selector.

## Least-privilege credential lifecycle

The PoC uses pre-existing administrator CloudConnections for isolated thesis
accounts and creates Twin-scoped runtime identities only where required by the
deployment graph. A production-oriented follow-up could generate reduced
deployment principals, rotate and revoke them, integrate organization policy,
and formally verify permissions. This requires a dedicated threat model,
provider-specific recovery procedures and operational ownership.

## Mutable deployments

The PoC keeps deployed Twins immutable. Supporting in-place changes would
require optimizer invalidation, Terraform replacement analysis, state migration,
rollback, partial-failure recovery and a new identity/evidence model. Those
properties should be evaluated together rather than added as a simple Edit
button.

## Broader runtime and operational evidence

Future evaluations could study concurrent deployments, larger workloads,
long-running reliability, cost reconciliation against provider bills, regional
availability, additional services and organization-scale account boundaries.
They are not implied by the nine supervised Small scenarios used in this
thesis.
