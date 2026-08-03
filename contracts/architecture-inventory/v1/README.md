# Current architecture inventory v1

`current-graph.json` is the audit source of truth for the deployable
five-layer baseline. It records current implementation evidence; it does not
approve inherited components or make Phase 8.1 retain/replace/remove decisions.

`five-layer-baseline-v1-decision.json` is the immutable Phase 8.1 historical
target-decision source of truth. It covers the components and edges of its
Phase 8.0 evidence cut, but does not claim that the target is implemented.
`baseline-decision.schema.json` and the semantic checker enforce its
closed-world coverage, proofs, provider admissibility, binding sources, scope,
content digest, and frozen Phase 8.0 source digest. Later current-graph drift
does not rewrite this paper-compatible decision.

## Canonical form

- JSON object keys are sorted lexicographically and serialized with two-space
  indentation plus one final newline.
- Entity arrays are sorted by their primary stable ID. Other arrays are sorted
  unless their order is itself a contract, such as the Optimizer slot order.
- `content_digest` is `sha256:` plus the SHA-256 of compact, sorted JSON after
  removing `generated_at` and `content_digest`.
- `audited_source_tree_digest` hashes a sorted list of repository-relative
  path/content-SHA pairs. Inventory files, generated documentation, Git data,
  ignored files, credentials, runtime state, and caches are outside that input.
- `source_commit` is provenance for the audited tree and is intentionally not
  compared with `HEAD`.

Run the non-mutating drift gate from the repository root:

```bash
python3 scripts/check_architecture_inventory.py
```

Regeneration is an explicit reviewer action:

```bash
python3 scripts/check_architecture_inventory.py --write
python3 scripts/check_architecture_inventory.py --write-baseline-decision
python3 scripts/check_architecture_inventory.py
```

The checker emits only bounded IDs and repository-relative paths. It never
prints file contents, payloads, credentials, endpoints, or physical resource
identifiers.
