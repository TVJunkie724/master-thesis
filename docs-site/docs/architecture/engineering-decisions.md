# Engineering Decisions

This page explains the major technical decisions that maintainers must understand when
changing the current platform. It describes implemented architecture outcomes, not a
chronological commit log or a research evaluation.

## Management API As Orchestrator

**Decision:** place user/twin lifecycle, persistence, security, and cross-service
coordination behind one Management API.

**Reason:** direct UI calls to independently evolved services duplicated error/auth
logic and exposed unstable internal contracts. The orchestrator creates one ownership
and authorization boundary while preserving Optimizer/Deployer specialization.

## Relational Application State

**Decision:** use SQLAlchemy with SQLite for the local single-node runtime.

**Reason:** users, twins, configurations, credential references, calculations, and
operations are relational and transactional. SQLite minimizes deployment complexity.
The trade-off is that horizontal replicas and production HA require a managed relational
database and stronger migration/backup operations.

## Credential SSOT

**Decision:** persist reusable credentials as encrypted, user-scoped CloudConnections;
keep bootstrap/admin input transient.

**Reason:** workspace copies and Docker-mounted plaintext created duplication, unclear
ownership, accidental disclosure, and difficult rotation. Metadata/purpose/defaults
make account reuse explicit without returning secrets.

## File Registry Plus Operational Database

**Decision:** keep pricing intents/mappings/formula contracts in versioned YAML, while
persisting refresh runs, candidate reports, user decisions, and calculations in the
Management API DB.

**Reason:** executable mappings need reviewable diffs, branch/CI validation, and code
coupling. Operational history needs transactions, querying, user scope, and retention.
A mirrored editable DB would create two competing sources of truth.

## Deterministic Pricing With Human Review

**Decision:** provider rows pass typed intent/filter/normalization/publication gates;
ambiguous cases expose evidence and require a reviewed mapping decision.

**Reason:** catalog text and dimensions drift. String matching alone is not sufficiently
reliable, while opaque AI-only selection is not reproducible or auditable. The contract
reserves an advisory AI result for future work, but no OpenAI adapter is currently
enabled; deterministic evidence and user review remain authoritative.

Tiered provider prices opt into a separate `tier_series` selection mode. A series must
contain a zero threshold, unique non-negative lower bounds, numeric non-negative prices,
and one reviewed meter identity. Candidate IDs combine meter, product, SKU, price type,
and tier because Azure may reuse a meter ID across Consumption and Reservation rows.
Failed or review-required refreshes cannot overwrite the last-known-good snapshot.

## Optimization Bundles

**Decision:** bind optimization metric, intent group, calculation model, formula set,
workload/provider contracts, scoring, and result schema into a validated bundle/profile.

**Reason:** changing only a fetcher or formula can otherwise produce semantically
inconsistent comparisons. Bundling makes cost executable today and future objectives
visible without falsely implementing them.

## Terraform In Ephemeral Workspaces

**Decision:** retain Terraform but generate/run it from manifest-backed isolated
workspaces, then synchronize only durable allowlisted outputs.

**Reason:** Terraform provides state, planning, idempotence, and destroy semantics.
The old shared mutable folder was the debt, not file-based infrastructure definition
itself. Isolation protects templates, supports concurrency, and constrains artifacts.

## Riverpod Plus BLoC

**Decision:** Riverpod composes application dependencies/simple global state; BLoC owns
complex feature workflows.

**Reason:** forcing every concern into one mechanism would either inflate global state
or hide workflow transitions. The rule is exclusive ownership per mutable feature, with
Riverpod injecting dependencies into route-scoped BLoCs.

## Offline Demo Adapters

**Decision:** implement the demo behind the same Flutter API/log interfaces.

**Reason:** every screen can be inspected without credentials or cloud cost, while
production code avoids scattered demo branches and the adapter contract remains tested.
