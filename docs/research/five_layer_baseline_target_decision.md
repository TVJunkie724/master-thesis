---
title: "Five-Layer Offline Baseline Decision"
description: "Methodological role of the non-deployable five-layer comparison baseline."
tags: [architecture, baseline, digital-twin, evaluation]
lastUpdated: "2026-08-27"
version: "2.0"
---

# Five-layer offline baseline decision

## Decision

Five-layer v1 is retained only inside the Optimizer as a reproducible comparison
baseline derived from the predecessor work. It represents Ingestion,
Processing, Storage, Twin state and Visualization. Storage tiers may remain
separate cost slots while belonging to one scientific storage responsibility.

The baseline is not a public architecture contract. It cannot be selected,
persisted as a new Twin architecture, sent to the Deployer, projected into
Terraform, rendered as a workflow choice, or used as live evaluation evidence.

## Methodological purpose

Keeping the original calculation boundary allows the thesis to:

- reproduce predecessor behavior under fixed inputs;
- explain why Eventing must become an explicit responsibility in the evaluated
  Six-layer architecture;
- distinguish a change in architecture semantics from a change in price or
  workload assumptions; and
- document which comparison claims are offline only.

## Six-layer distinction

The deployable `six-layer-eventing@1` contract independently owns Eventing
placement, fan-out, retry/dead-letter behavior, replay/ordering claims,
cross-provider routes, observability, verification and cost attribution. It is
standalone and does not inherit from the Five-layer baseline.

This separation avoids two invalid interpretations: that the baseline already
proves the Eventing behavior, or that the active architecture is merely a
runtime switch on top of an older deployment profile.

## Evidence boundary

Baseline results must be labelled offline and must record the same workload,
pricing snapshot and formula provenance used for comparison. Only the fixed
Six-layer workflow contributes provider readiness, Terraform, telemetry,
access-handoff or Destroy evidence to the thesis evaluation.
