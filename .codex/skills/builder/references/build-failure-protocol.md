# Build Failure Protocol

When `flutter analyze`, `flutter test`, or `flutter build` fails, follow these 5 steps:

1. **Read the error message carefully** — Understand the exact failure
2. **Identify the root cause** — Missing import, type mismatch, null safety, missing BLoC registration, missing dependency in `pubspec.yaml`, missing `MultiBlocProvider` ancestor, broken `go_router` route, missing asset declaration
3. **Fix the issue** in the appropriate file
4. **Re-run the failing command** to verify the fix
5. **If unable to fix after 3 attempts** — Report the issue. Do not keep guessing.

## Critical Rules

- If the build is broken BEFORE starting work: **STOP**. Do NOT proceed with implementation until the build is green. Report the failure and wait for resolution.
- If `flutter analyze` fails DURING implementation: **STOP immediately**. Do NOT continue to the next layer. Fix the current layer first.
- If `flutter test` fails: distinguish between (a) tests testing the new code (fix the code or fix the test, decide consciously) and (b) pre-existing tests now broken (your change has a side effect — find it).
- Never proceed with a broken build. A broken build is a blocking issue.

## Common Failure Modes

| Symptom | Likely cause | Fix direction |
|---------|--------------|---------------|
| `Undefined name 'context.read<XBloc>()'` | `BlocProvider<XBloc>` missing higher in the tree | Add `BlocProvider` in the screen scaffold or `app.dart` |
| `Bad state: No element` from a `Bloc` event handler | State not initialized; reading optional field as required | Add a guard or restructure the state |
| `late initialization error` on `Dio` / service | DI wiring missing | Provide the service via constructor, not via lazy `late` |
| `flutter analyze` complains about missing `const` | Easy fix — add `const` everywhere it asks | Keep `const` discipline |
| Web build fails on a dart:io import | Some package only works on Native, not on Web | Use a Web-safe alternative or guard behind `kIsWeb` |
| `EventSource` doesn't reconnect | Manual reconnect logic missing | Wrap the subscription in a `StreamController` with retry-with-backoff |
| Wizard step refuses to advance | `WizardBloc` validation fails silently | Check the actual emitted state, surface the failure to the user |

## After Fixing

Rerun the full pipeline before moving on:

```bash
cd twin2multicloud_flutter
flutter analyze
flutter test
flutter build web
```

Only proceed when all three are green.
