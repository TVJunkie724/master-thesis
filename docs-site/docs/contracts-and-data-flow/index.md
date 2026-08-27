# Contracts and Data Flow

This section describes the implemented thesis-PoC boundaries.

1. [System Boundaries](system-boundaries.md)
2. [Cross-Project Contract Map](contract-map.md)
3. [Canonical Architecture Contract](canonical-architecture-contract.md)
4. [Pricing and Cost Optimization](pricing-optimization.md)
5. [User-Function Extensions](user-function-extensions.md)
6. [Deployment Lifecycle](deployment-lifecycle.md)
7. [Credentials and Trust](credentials-and-trust.md)
8. [State Ownership](state-ownership.md)

Flutter communicates only with Management. Exact calculation evidence flows
from Optimizer to Management; immutable operation evidence flows from Deployer
to Management. Credentials flow only from Management to Deployer for the
current request.

Schema versions identify durable wire formats. They do not imply multiple
selectable architectures or objectives. Contract diagrams show ownership and
data direction, not permission for a new direct network dependency.

After changing a shared contract, synchronize all generated copies and run the
repository contract/deployment gates. Those gates are offline and do not
constitute live provider evidence.
