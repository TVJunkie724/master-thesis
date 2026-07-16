# Developer Guide

Start at the repository root and preserve service ownership. The most important rule is
that a user-facing feature crosses the Management API rather than coupling Flutter to
an internal service.

## Change Workflow

1. identify the state owner and current contract;
2. update the relevant GitHub issue/plan for material architecture work;
3. change the owning service and its tests;
4. update typed downstream/client contracts;
5. update Flutter network and demo adapters if user-visible;
6. run safe project gates;
7. update current documentation and provenance when behavior/evolution changes.

- [Project Setup](setup.md)
- [Project Structure](project-structure.md)
- [API and Contracts](contracts.md)
- [Extension Points](extension-points.md)
- [Testing](testing.md)
