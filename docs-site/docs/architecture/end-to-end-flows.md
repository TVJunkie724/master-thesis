# End-to-End Flows

## Configuration And Optimization

```text
User input
  -> Flutter Configuration Workspace
  -> typed workload parameter draft
  -> POST durable optimizer run
  -> Management application service
  -> owner-scoped exact AWS + Azure + GCP catalog context
  -> Optimizer calculation request
  -> active optimization profile
       metric provider: cost
       pricing intent group: cost
       calculation model: cost_model_v1
       formula set + provider contracts
       scoring strategy: minimum cost
  -> typed result + trace metadata + identical catalog context
  -> Management contract validation
  -> atomic calculation run/items/result/path persistence
  -> read-only Flutter review
```

The user expresses workload quantities. Provider pricing models are not forced into
one raw unit; provider contracts and formulas normalize their own billable units into
the common output metric `USD/month`. Flutter cannot author or overwrite calculation
results, transfer evidence, catalog references, or the deployment path.

## Pricing Refresh And Review

```text
User selects provider and confirms source scope
  -> AWS/GCP: Management API resolves owned pricing CloudConnection
  -> Azure: public catalog request uses selected pricing region
  -> provider refresh starts in Optimizer
  -> provider API rows / official-static classifications
  -> raw evidence retained
  -> intent contract filters and normalizes candidates
  -> immutable provider-region candidate
  -> publishable match? ---- yes ---> atomic regional published pointer
              |
              no
              v
       review-required candidate; published reference remains active
              |
       user records a decision in Management API DB
              |
       future refresh reuses reviewed mapping, not a price override
```

An emergency fallback is diagnostic, never the target source. Review decisions may
select a mapping but are forbidden from storing a replacement price. Evidence and
normalization remain inspectable. Calculation resolves the newest usable owner
refresh reference for each provider, otherwise the reviewed baseline. It verifies
each exact identity before formula execution; Flutter never exports or authors
pricing evidence.

## Credential Bootstrap And Use

```text
transient admin/bootstrap credential
  -> provider bootstrap service
  -> create/version least-privilege credential material
  -> encrypt and persist CloudConnection
  -> discard admin plaintext
  -> validate/preflight by purpose
  -> bind deployment connection to twin or set user pricing default
```

Bootstrap credentials are not intended to become reusable stored admin credentials.
Pricing credentials are user-level defaults; deployment credentials can be bound to
individual twins.

## Deployment

```text
configured twin
  -> Management API readiness + preflight
  -> build canonical deployment archive
       deployment_manifest.json (v1.0)
       generated configuration
       user artifacts / scene assets
       transient credential context
  -> Deployer validates archive and stages operation package
  -> one-use package token identifies exact accepted bytes
  -> deploy/destroy request acquires token
  -> isolated ephemeral workspace
  -> Terraform-first provider execution + bounded SDK operations
  -> allowlisted runtime outputs synchronized
  -> structured logs/results returned
  -> Management API persists operation and lifecycle result
  -> Flutter observes REST status and SSE logs
```

The canonical operation never mutates the versioned template. Generic project-file
APIs hide credential files and reject traversal.

## Offline Demo

```text
config/demo.json
  -> runtime composition
  -> DemoManagementApi + DemoLogStreamClient
  -> scenario fixture store
  -> same Flutter screens and typed ManagementApi interface
  -X-> no HTTP, no Docker, no cloud provider
```

The demo is an adapter replacement, not scattered UI conditionals or a fake backend
server. It exists for repeatable product walkthroughs and screen coverage.
