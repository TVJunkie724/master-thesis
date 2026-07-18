# Resolved Deployment Reproducibility Evidence

## Purpose

This research note records the methodological reason for the
`ResolvedDeploymentSpecification v1` work. It is thesis evidence, not
operational user documentation.

The cost optimizer originally selected providers and services while parts of
the Deployer retained independent defaults for SKU, capacity, runtime memory,
storage class, and schedules. A mathematically cheapest result therefore did
not necessarily prove that Terraform would deploy the infrastructure whose
price had been calculated.

That mismatch is a threat to construct validity:

> A cost comparison is meaningful only if each reported candidate is
> functionally admissible and the evaluated deployment parameters are the same
> parameters enforced by the infrastructure implementation.

## Assurance Argument

The implemented assurance chain is:

```text
fixed workload + immutable provider-region catalog references
  -> provider formula and explicit deployment selections
  -> complete-path cost optimization
  -> ResolvedDeploymentSpecification v1
  -> canonical SHA-256 digest
  -> atomic Management API persistence
  -> selected calculation-run identity
  -> DeploymentManifest v2
  -> Deployer semantic preflight
  -> allowlisted typed tfvars
  -> Terraform variable validation
  -> provider resource attributes
```

Each boundary has one owner:

| Boundary | Owner | Evidence |
| --- | --- | --- |
| workload to tier/SKU/capacity | Optimizer formulas | provider tier tests and hard expected cases |
| winning path to component dimensions | Optimizer deployment registry | schema and semantic contract tests |
| immutable result and digest | Management API | transaction, round-trip, selection, and tamper tests |
| selected run to operation package | Management API | Manifest v2 contract tests |
| manifest to tfvars | Deployer | strict preflight and allowlist tests |
| tfvars to resources | Terraform | parsed source bindings and native mock plans |

No downstream boundary may fill a missing deployable value from a local
default. Progressive billing tiers, account-scoped plans, and formula
assumptions that Terraform cannot enforce remain explicit evidence and are
forbidden as tfvars.

## Independent Verification Matrix

The production source of truth is `deployment-dimensions.json`. A separate
`verification-matrix.json` contains reviewed expected outcomes and is never
read by runtime code. This separation avoids deriving actual and expected
values through the same implementation.

The current matrix covers:

- 31 components with deployable dimensions;
- 54 component-to-target bindings;
- 50 unique Terraform targets;
- four complete representative provider paths;
- Azure IoT Hub F1, S1, S2, and S3 formula/capacity cases;
- both source-owned storage transition runtimes;
- receiver-owned cross-cloud writer/glue components.

Tests generate all 27 combinations of AWS, Azure, and GCP hot, cool, and
archive storage. They assert source runtime ownership, destination storage
class, cross-provider receiver glue, and absence of unnecessary same-provider
glue.

Three native `terraform test` plans use mock providers and production package
builders. They inspect representative AWS, Azure, and GCP resource attributes
without provider credentials, cloud API requests, `terraform apply`, state
files, or billable infrastructure.

## Failure Model

The chain fails closed for:

- unsupported or missing schema versions;
- missing, duplicate, unknown, or reordered components/dimensions;
- provider, slot, transition-owner, or receiver-owner drift;
- unsupported SKU/capacity combinations;
- missing formula, evidence, catalog, run, or digest identity;
- unknown Terraform targets or evidence-only tfvars;
- stale selected calculations and tampered manifests;
- secret-like fields and unbounded downstream diagnostics.

Failures occur before credential resolution, package staging, Terraform
execution, or deployment side effects wherever that boundary can make the
decision.

## Reproducible Gate

The focused evidence command is:

```bash
./thesis.sh test deployment-contract --focused
```

The complete thesis/handoff gate is:

```bash
./thesis.sh test deployment-contract
```

The command removes provider credential environment variables, rejects live
E2E and credential-overlay modes, uses isolated ephemeral application secrets,
and cleans verification containers, networks, and volumes on success or
failure. The complete mode adds all safe project suites, static/security
analysis, Flutter builds, strict documentation, and repository checks.

## Scope And Limitations

This evidence establishes internal reproducibility for the closed-world
`five-layer-baseline@1`. It does not prove:

- that provider catalog APIs will never drift;
- that a supervised real-cloud deployment currently succeeds;
- that deployed metering equals every provider invoice;
- that the five-layer topology is the best Digital Twin architecture;
- that future architecture profiles or Eventing components inherit v1
  mappings without a new reviewed contract.

Live provider validation and final application E2E remain deliberately
deferred. Architecture-profile and Eventing work must preserve this assurance
principle while introducing versioned profile-specific components and edges.
