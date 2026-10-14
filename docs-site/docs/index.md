# Twin2MultiCloud PoC

Twin2MultiCloud connects Digital Twin cost optimization with multi-cloud
deployment. It extends two predecessor projects with a Management API and
Flutter UI.

## Start here

| Question | Read |
|---|---|
| How do I run it? | [Quickstart](getting-started/fresh-clone.md) |
| What can I try and expect? | [PoC Walkthrough](user-guide/multi-cloud-walkthrough.md) |
| How does it work? | [System Context](architecture/system-context.md) |
| What is implemented and what remains open? | [Results and Limits](runtime/known-limitations.md) |
| Why was it built this way? | [Engineering Decisions](architecture/engineering-decisions.md) |

The **Reference** navigation contains service internals, contracts, operations
and development details. It is not required reading for the first walkthrough.

## Scope

The PoC estimates monthly cost for a bounded five-layer Digital Twin model and
preserves the selected calculation as deployment evidence. The Management API
coordinates configuration, credentials and execution; Flutter calls only that API.

The offline demo is ready for a repeatable UI walkthrough. Local startup does
not require cloud credentials. New deployments require a resolved architecture
and Manifest v3, while architecture-profile resolution defaults to off.
See [Results and Limits](runtime/known-limitations.md) before using cloud operations.

This is a research prototype. Implemented code, offline verification and
successful live-cloud execution are distinct evidence levels.

## Documentation boundaries

This site describes the current implementation and how to use it. Scientific
reasoning and evaluation design live in
[Research Notes](https://github.com/TVJunkie724/master-thesis/tree/master/docs/research).
[Project evolution](architecture/evolution.md) and
[source provenance](references/source-provenance.md) explain the predecessors.

Use [Troubleshooting](runtime/troubleshooting.md) when a local step fails.
