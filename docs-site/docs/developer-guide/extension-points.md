# Extension boundaries

The PoC keeps a few clean internal boundaries so its design is understandable
and testable. It does not expose unused extensions as runtime capabilities.

## Cost calculation

Provider calculators implement shared typed workload and result contracts. A
new provider component must add formula provenance, pricing evidence, unit
normalization, capability admission and deterministic tests. Monetary cost is
the only scoring strategy used by the application.

Other objectives belong to future research until their measurements,
normalization and evaluation method are defined. Do not add disabled objective
descriptors or a public selector.

## Provider deployment components

Provider-specific implementations are bound through the canonical Six-layer
component and edge definitions. A new component requires matching package,
Terraform, identity, permission, observability, verification, cleanup and cost
evidence. It cannot become selectable merely by registering a class.

## Bounded user functions

The typed Twin configuration accepts only the reviewed processor, action and
feedback source shapes. Validation, size limits, supported runtimes and
provider adapters are closed-world. See User-Function Extension Development
for the retained boundary.

## Future architecture variants

An alternative architecture is a separate research design with its own
contract and evaluation, not a child profile or plugin of
`six-layer-eventing@1`. The conceptual boundary is summarized in
`docs/future-work.md`.
