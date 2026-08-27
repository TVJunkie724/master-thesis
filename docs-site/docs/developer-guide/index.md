# Developer Guide

Start at the repository root and preserve service ownership. The most important rule is
that a user-facing feature crosses the Management API rather than coupling Flutter to
an internal service.

## Change Workflow

1. identify the state owner and current contract;
2. map material work to the active thesis phase and use one temporary plan if needed;
3. change the owning service and its tests;
4. update typed downstream/client contracts;
5. update Flutter network and demo adapters if user-visible;
6. run safe project gates;
7. update current documentation and durable decisions, then remove completed
   temporary planning artifacts.

- [Project Setup](setup.md)
- [Project Structure](project-structure.md)
- [API and Contracts](contracts.md)
- [User-Function Extension Development](user-function-extensions.md)
- [Extension Points](extension-points.md)
- [Testing](testing.md)
