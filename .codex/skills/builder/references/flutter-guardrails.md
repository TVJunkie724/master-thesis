# Flutter Guardrails — Twin2MultiCloud Frontend

Read and apply ALL guardrails before any UI work. These rules are project-specific to `twin2multicloud_flutter` and apply across every UI-* skill.

## 1. Project Identity

- **App**: `twin2multicloud_flutter` — the Flutter UI of the Twin2MultiCloud platform (the "Orchestrator" front-end in the 5-Layer Digital-Twin architecture).
- **Targets**: Desktop (Linux, macOS, Windows) and Web. **Mobile is NOT supported** — see commit `f135bac` (`drop mobile support`). Do not add Android/iOS code paths.
- **Companion projects** (do NOT touch from a UI task):
  - `2-twin2clouds` — cost optimizer (port 5003)
  - `3-cloud-deployer` — cloud deployer (port 5004)
  - `twin2multicloud_backend` / Management API (port 5005)

## 2. Mandatory Reading Before Any UI Work

| Document | Why |
|----------|-----|
| `FRONTEND_ARCHITECTURE.md` | Architecture, screen wireframes, twin states, BLoC layout |
| `integration_vision.md` | 5-Layer Architecture, cross-project responsibilities |
| `twin2multicloud_flutter/README.md` | Project-local conventions |
| `ONBOARDING.md` | Cross-project onboarding |

If a referenced document is missing, STOP and request it before continuing.

## 3. State Management — `flutter_bloc`

This project uses the **BLoC pattern** (`flutter_bloc`), NOT Riverpod. Existing wiring lives under `twin2multicloud_flutter/lib/bloc/`:

```
lib/bloc/
├── wizard/        → WizardBloc, WizardEvent, WizardState
└── twin_overview/ → TwinOverviewBloc and friends
```

| Rule | Why |
|------|-----|
| **One BLoC per feature**, owned by the smart widget at the top of the screen subtree | Predictable ownership — no global state surprises |
| **Events in, States out** — never call methods on a BLoC from a dumb widget | Keeps presentation reusable and testable |
| **Immutable state with `copyWith()`** | Prevents mutation bugs, enables `Equatable` comparison |
| **Always handle loading / data / error / empty** | Users must never see a blank screen |
| **Dispose subscriptions** in `close()` | Memory leaks are production defects |

## 4. Architectural Layers

| Layer | Folder | Rule |
|-------|--------|------|
| Presentation | `lib/screens/`, `lib/widgets/` | Pure UI, no HTTP, no business logic |
| State | `lib/bloc/` | Holds state, dispatches events, calls services |
| Services | `lib/services/` | Talks to Management API, Optimizer, Deployer over HTTP/SSE |
| Models | `lib/models/` | Plain Dart DTOs / value objects |
| Theme | `lib/theme/` | `colors.dart`, `spacing.dart` — single source of design tokens |
| Config | `lib/config/` | Endpoints, environment switches |

**Smart/Dumb widget split:** one "smart" widget per screen consumes BLoC state via `BlocBuilder`/`BlocListener`. All children are "dumb" — they receive data through their constructor.

## 5. Backend Integration

| Concern | Choice |
|---------|--------|
| HTTP client | `dio` |
| Real-time logs | **SSE** via `eventsource_client` (NOT WebSocket, NOT polling) |
| Auth | JWT issued by Management API; OAuth flows are provider-pluggable (Google first) |
| Routing | `go_router` (URL-based, required for Web back/forward) |

**Architecture rule** (from `integration_vision.md`): Flutter NEVER calls Deployer or Optimizer directly. Always go through Management API (`Flutter → Management API → {Deployer, Optimizer}`). Any direct call from Flutter to port 5003 / 5004 is a defect.

## 6. Design Tokens — Zero Tolerance for Hardcoded Values

- All colors come from `lib/theme/colors.dart`. New colors are added to the token file first, then referenced.
- All spacing comes from `lib/theme/spacing.dart`. Magic numbers (`16`, `8`, `24` …) in widget code are a defect.
- Typography comes from `ThemeData` text styles. Inline `TextStyle` constructors are a defect unless they only override a theme style.
- Strings: when localization is added later, hardcoded user-facing strings will become defects. For now, group them into a single constants file per screen so the future migration is mechanical.

## 7. Icons

The project uses **Material `Icons`** (Flutter built-in). There is no proprietary icon set. If a Material icon is wrong for the brand, raise a concept item — do not introduce a third-party icon library without architect approval.

## 8. ASCII Diagrams Only

| Forbidden | Required |
|-----------|----------|
| Mermaid | ASCII box drawings (see `FRONTEND_ARCHITECTURE.md` for examples) |
| Pasted screenshots in plans | ASCII layout + widget tree |

ASCII is universal: it diffs cleanly, renders in every terminal, and survives copy-paste between agents.

## 9. Build / Analyze Commands

```bash
cd twin2multicloud_flutter
flutter pub get
flutter analyze            # zero issues required
flutter test               # unit + widget tests
flutter build linux        # or macos / windows / web
flutter run -d chrome      # for Web dev
flutter run -d linux       # for Desktop dev
```

If `flutter analyze` reports anything, STOP and fix before continuing.

## 10. Backend Services for Integration / E2E Tests

The Flutter app talks to live services. Bring them up via Docker:

```bash
docker compose up -d                      # all services
docker ps                                 # confirm
# Optimizer    → http://localhost:5003
# Deployer     → http://localhost:5004
# Management   → http://localhost:5005   (when implemented)
```

| Test type | Allowed | Notes |
|-----------|---------|-------|
| Unit / widget | ✅ Always | `flutter test` |
| Integration against running Docker stack | ✅ With user awareness | Hits real local APIs, no mocks |
| **E2E that deploys real cloud resources** | ❌ Forbidden by default | Costs real money. Requires explicit user instruction. See `onboarding` skill. |

Integration tests use the **real HTTP API**. No mocking the dio client at the integration level. Mock only at the unit level when isolating a specific BLoC from its services.

## 11. Git Workflow

- All UI work happens on the `ai/dev` branch (see `onboarding` skill — Step 0).
- Commit format: `[AI-MMDD-xxxx] <type>: <description>` (e.g. `[AI-0413-skil] feat(flutter): add dashboard stat cards`).
- Never push — the user pushes themselves.
- Merges into `master`: merge commits only, no rebase.

## 12. Files / Folders You Must NOT Touch from a UI Task

| Path | Why |
|------|-----|
| `2-twin2clouds/` | Optimizer backend — separate concern |
| `3-cloud-deployer/` | Deployer backend — separate concern |
| `twin2multicloud_backend/uploads/` | Runtime upload data — never commit |
| `twin2multicloud-latex/` | Thesis document |
| `*_credentials*.json` | Secrets — never commit, never read content into chat |
| `.ai-session.json` | Session state — read only when needed, do not commit |

## 13. Universal "Don'ts"

| Never | Why |
|-------|-----|
| `print()` in committed code | Use `debugPrint` in dev paths, structured logging otherwise |
| TODO / FIXME / HACK comments shipped to `master` | Either fix it or open a tracked item |
| Commented-out code in commits | Git history already preserves it |
| Hardcoded URLs / ports | Use `lib/config/` |
| Skip the loading / error / empty path | Every async branch needs all three |
| Direct widget-to-service calls | Always go through a BLoC |
| New widget without checking `lib/widgets/` first | Reuse before creating |

## 14. Quality Gate (Pre-Handoff)

Before reporting any UI work as complete:

- [ ] `flutter analyze` — zero issues
- [ ] `flutter test` — all green
- [ ] `flutter build <target>` — succeeds for Desktop AND Web
- [ ] No new hardcoded colors / spacings / strings
- [ ] All async branches have loading + error + empty states
- [ ] Smart/dumb split respected
- [ ] BLoC events / states match the plan
- [ ] No direct calls to Optimizer / Deployer from Flutter
- [ ] No mobile-only widgets / packages added
- [ ] Commit messages follow `[AI-MMDD-xxxx] type: …`
