# Test Plan Requirements

## Minimum Requirements per Testable Unit

- **≥ 2 Happy Path tests** — Core functionality works under normal conditions
- **≥ 2 Unhappy Path tests** — Graceful handling of failures, invalid input, missing data, Management API errors (4xx / 5xx), broken SSE connection
- **≥ 5 Edge Case tests** — Boundary conditions, race conditions, extreme values, rapid input, empty / null states, twin-state transitions, partial deployments

## Justification Rules

- **Fewer than 5 edge cases?** The plan MUST include a written justification explaining why fewer are sufficient for this specific unit.
- **More than 5 edge cases needed?** For complex components (state machines, multi-step wizard, real-time SSE streams, file-version diffing) 5 is a MINIMUM. Identify ALL relevant edge cases and include a justification for the additional complexity.
- **The goal is total coverage of every relevant scenario.** The number 5 is a baseline, not a ceiling.

## Test Types in This Project

| Type | Tooling | Where it runs | When |
|------|---------|---------------|------|
| Unit | `flutter test` | Host | Pure Dart logic, BLoC transitions, mappers |
| Widget | `flutter test` (`WidgetTester`) | Host | Single-widget rendering and interaction |
| Integration | `flutter test integration_test/` | Host (against Docker stack) | Full screen flows hitting the real Management API |
| **E2E that deploys real cloud** | — | — | **Forbidden by default.** Costs real money. Requires explicit user instruction. |

Integration tests use the **real Management API** running in Docker (`docker compose up -d`). No mocking the `dio` client at integration level. Mock only at the unit level when isolating a BLoC from its services.

## Test Case Format

For each testable unit, list tests in a table:

| # | Type | Test Description | Expected Outcome |
|---|------|------------------|------------------|
| 1 | Happy | Wizard Step 1 saves draft → state.draft persists across navigation | `WizardState.persisted == true`, twin appears in Dashboard with state `draft` |
| 2 | Happy | … | … |
| 3 | Unhappy | Management API returns 502 on `/twins/{id}/deploy` | Snackbar shown with retry button; twin state stays `configured` |
| 4 | Unhappy | … | … |
| 5 | Edge | SSE log stream drops mid-deployment | Reconnect attempted; UI shows "Reconnecting…" banner |
| 6 | Edge | … | … |
| ... | Edge | … | … |

## Asserts: Hard, Never Silent

Every test must contain **explicit assertions** on real values. A test that calls a function and doesn't assert anything passes silently and is useless. Common pitfalls:

- `expect(find.byType(Foo), findsWidgets)` — what counts as success? Always pin to `findsOneWidget` or an exact `findsNWidgets(n)` unless the variable is justified.
- `await tester.pumpAndSettle()` without an assertion afterwards is a smell.
- Mocks must verify the call (`verify(client.post(...)).called(1)`) — not just allow it.
