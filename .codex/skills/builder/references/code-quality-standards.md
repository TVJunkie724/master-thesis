# Code Quality Standards — Twin2MultiCloud Flutter

## Widget Patterns

| Pattern | Rule |
|---------|------|
| **Smart / Dumb Split** | One smart widget per screen consumes BLoC state via `BlocBuilder` / `BlocListener`. All children are dumb (receive data via constructor). |
| **`const` Constructors** | Use `const` constructors wherever possible. Mark widgets `const` when they can be. |
| **Keys** | Provide explicit keys for list items and widgets that move in the tree. |
| **Build Method** | Keep `build()` focused. Extract sub-trees into named methods or child widgets when they exceed ~30 lines. |
| **No Logic in Build** | No HTTP calls, no heavy computation, no side effects inside `build()`. Move them into the BLoC's event handler. |
| **Equality** | Custom widgets that compare for rebuilds use `Equatable` or override `==` / `hashCode`. |

## State Management — `flutter_bloc`

| Rule | Why |
|------|-----|
| One BLoC per feature, owned by the smart widget at the top of the screen subtree | Predictable ownership |
| Never access a BLoC from a "dumb" widget | Keeps them reusable and testable |
| Immutable state objects with `copyWith()` and `Equatable` | Prevents mutation bugs, enables value comparison |
| Handle ALL async states (loading / data / error / empty) | Users must never see a blank screen |
| Dispose subscriptions and controllers in `close()` | Memory leaks are production defects |
| Use `BlocListener` for navigation / snackbars; `BlocBuilder` for rebuilds | Don't trigger side effects from inside `build()` |

## Services Layer

| Rule | Why |
|------|-----|
| Services live in `lib/services/`, take a `Dio` instance via constructor | Testable in isolation |
| Services call **Management API only** (port 5005) | Architecture rule from `integration_vision.md` |
| SSE subscriptions wrapped in a `Stream<LogLine>` returned from the service | BLoC consumes a stream, not the raw `EventSource` |
| Errors mapped to typed exceptions (`ApiException`, `NetworkException`, `AuthException`) before reaching the BLoC | BLoC handles exceptions, not raw `DioError` |

## File Organization

| Rule | Why |
|------|-----|
| Follow the established folder structure under `lib/` (`bloc/`, `screens/`, `widgets/`, `services/`, `models/`, `theme/`, `config/`, `providers/`, `core/`, `utils/`) | Consistency across the codebase |
| One public widget per file | Findability — file name = widget name (snake_case file, PascalCase widget) |
| Group related private helpers at the bottom of the file | Keep the public API visible at the top |
| Import ordering: `dart:*` → `package:*` → relative project imports | Readability and convention compliance |
| BLoC files: `<feature>_bloc.dart`, `<feature>_event.dart`, `<feature>_state.dart` | Mirrors the existing `lib/bloc/wizard/` layout |

## Tokens & Theming

| Rule | Why |
|------|-----|
| All colors come from `lib/theme/colors.dart` | Single source of truth |
| All spacing comes from `lib/theme/spacing.dart` | No magic numbers |
| Typography comes from `ThemeData.textTheme` — inline `TextStyle` only when overriding a single property of a theme style | Consistent typography |
| New tokens are added to `lib/theme/` BEFORE any widget references them | Avoids "temporary" hardcoded values that never get cleaned up |

## Testing

| Rule | Why |
|------|-----|
| Every BLoC has unit tests covering all event → state transitions | BLoC is pure logic — easy to test |
| Every smart widget has at least one widget test rendering its happy path | Protects against accidental rebuild regressions |
| Integration tests hit the real Management API in Docker | No mocks at integration level — see `../architect/references/test-plan-requirements.md` |
| Tests assert real values (`expect(state.twins.length, 3)`) — not just "something rendered" | No silent passes |

## Forbidden in committed code

- `print()` (use `debugPrint` in dev paths only)
- TODO / FIXME / HACK comments
- Commented-out code (git history preserves it)
- Direct widget-to-service calls (always through a BLoC)
- Direct calls to ports 5003 / 5004
- Mobile-only widgets / packages (`Cupertino*` for mobile, `permission_handler`, etc.)
