---
title: "Web and All-Desktop Flutter Support"
status: "Implemented"
issue: 109
baseBranch: master
featureBranch: codex/all-desktop-platform-support
lastUpdated: "2026-07-16"
---

# Web and All-Desktop Flutter Support

## 1. Decision

Twin2MultiCloud supports exactly these Flutter targets:

| Target | Product support | Automated evidence |
|---|---|---|
| Web | Supported | Linux-hosted Web release build |
| macOS desktop | Supported | Native macOS release build |
| Windows desktop | Supported | Native Windows release build |
| Linux desktop | Supported | Native Linux release build |
| Android, iOS, Fuchsia | Unsupported | Runtime classification tests reject them |

This is an application-wide contract. Authentication, configuration, demo
mode, file handling, pricing review, deployment workflows, startup guidance,
and documentation must not narrow the supported desktop set to macOS.

Build support does not imply signed installers, notarization, store delivery,
or platform certification. Those remain explicit release-engineering work.

Tracking issue: [#109 Establish Web and all-desktop Flutter support gates](https://github.com/TVJunkie724/master-thesis/issues/109).

## 2. Current Finding

The Flutter application already contains Web, macOS, Windows, and Linux runner
projects, and most infrastructure adapters are desktop-neutral. However:

- `thesis.sh` defaults unconditionally to `macos`;
- local quality gates build only Web and macOS;
- no native Windows or Linux build gate exists;
- the runtime guard names mobile platforms but does not express one reusable
  supported-platform contract;
- canonical setup, architecture, authentication, and testing documentation
  repeatedly describes only Web/macOS.

This mismatch is an architecture and handoff defect: source presence is not
evidence that a target continues to compile.

## 3. Scope And Boundaries

### In scope

1. Introduce one typed Flutter platform classifier for all supported and
   rejected targets.
2. Unit-test Web, macOS, Windows, Linux, Android, iOS, and Fuchsia outcomes.
3. Make `thesis.sh` detect the native host target when no explicit device is
   supplied. Preserve `--device` and `THESIS_FLUTTER_DEVICE` overrides.
4. Make the local frontend gate build Web plus the current host desktop.
5. Run the read-only integration gate on the current host desktop.
6. Add least-privilege GitHub Actions jobs for static/test/Web gates and native
   macOS, Windows, and Linux release builds.
7. Audit direct `dart:io`, browser-launch, file-picker, download, and generated
   plugin surfaces for all supported targets.
8. Publish one canonical support matrix and update all current documentation
   that defines startup, testing, architecture, authentication, or support.

### Out of scope

- mobile support;
- signed or notarized packages and installers;
- App Store, Microsoft Store, or Linux package-repository publication;
- live cloud operations or live external-identity authentication;
- rewriting historical implementation evidence solely to replace old wording.

## 4. Implementation Slices

### Slice A: Runtime and local entrypoint

- Replace direct `dart:io Platform` checks in `main.dart` with a pure typed
  classifier based on Flutter's target-platform abstraction.
- Reject every target outside the explicit support set before runtime
  composition starts.
- Resolve the default `thesis.sh` device from `uname`: Darwin to `macos`, Linux
  to `linux`, and MINGW/MSYS/CYGWIN to `windows`. Unknown hosts fail with a
  deterministic remediation message.
- Keep Chrome/Web selectable explicitly because a host cannot infer whether a
  developer intends a browser or native desktop run.
- Use the resolved host desktop in local build and integration gates.
- Support Windows startup through Git Bash; do not imply native PowerShell
  compatibility for a Bash entrypoint.

### Slice B: Cross-platform delivery gates

- Add a repository workflow with read-only permissions and concurrency
  cancellation.
- Pin third-party action revisions and Flutter `3.44.0`.
- Run architecture checks, formatting, analyzer, full Flutter tests, and the
  Web release build on Linux.
- Build macOS, Windows, and Linux release artifacts on native GitHub-hosted
  runners with the tracked production example configuration.
- Install only the Linux packages required by the Flutter desktop toolchain.
- Use fail-fast false for the native matrix so one platform cannot hide
  evidence from the others.

### Slice C: Canonical documentation

- Add `Supported Platforms` to the Getting Started navigation.
- Update root and Flutter READMEs, fresh-clone setup, runtime configuration,
  developer setup/testing, system context, Flutter component, authentication,
  and thesis evidence pages.
- State the Windows Git Bash prerequisite for `thesis.sh` and host-specific
  Flutter/Docker prerequisites.
- Distinguish application build support from installer/signing readiness.
- Amend completed authentication and cross-cutting quality records with the
  expanded current support contract while retaining their dated local
  evidence.

## 5. Error Handling And Security

- Unsupported targets fail before API clients, auth state, or repositories are
  created.
- An unsupported or unrecognized shell host fails before Flutter is launched;
  it never silently falls back to macOS.
- CI has `contents: read` only, receives no cloud credentials, and uses the
  secret-free tracked production example config.
- Build jobs perform no backend startup, provider refresh, deployment, or
  external authentication.
- No workflow uploads generated configs, tokens, credentials, or local data.

## 6. Verification Gates

### Focused local gates

```bash
bash -n thesis.sh
python3 -m unittest scripts.tests.test_check_flutter_architecture
cd twin2multicloud_flutter && flutter test test/config/supported_platforms_test.dart
```

### Full local gates

```bash
./thesis.sh test frontend
THESIS_DOCKER_CONTEXT=orbstack ./thesis.sh test frontend-integration
docker compose --profile docs run --rm docs mkdocs build --strict
git diff --check
```

The macOS host verifies Web and macOS locally. It must not be used as evidence
for Windows or Linux compilation.

### Native CI gates

```text
quality-and-web  -> Ubuntu -> format + analyze + tests + Web release
desktop-macos   -> macOS  -> macOS release
desktop-windows -> Windows -> Windows release
desktop-linux   -> Ubuntu -> Linux release
```

All four jobs must pass before the support claim is considered verified.

## 7. Definition Of Done

- [x] One typed runtime contract covers every Flutter target.
- [x] Focused tests prove all supported and unsupported classifications.
- [x] The root entrypoint auto-selects macOS, Windows, or Linux without a
      macOS fallback.
- [x] Local gates build Web plus the current host desktop.
- [x] Native CI builds Web, macOS, Windows, and Linux successfully.
- [x] Platform-specific adapters compile on every supported target.
- [x] Canonical documentation states one consistent platform matrix.
- [x] Historical evidence is clearly distinguished from current support.
- [x] Full Flutter, integration, strict docs, and diff-hygiene gates pass.
- [x] Two review passes have no unresolved findings.
- [x] Structured commits reference [#109 Establish Web and all-desktop Flutter support gates](https://github.com/TVJunkie724/master-thesis/issues/109).

## 8. Verification Evidence

Completed on 2026-07-16:

| Gate | Result |
|---|---|
| Repository Python self-tests | 30 passed, including entrypoint and architecture contracts |
| Flutter unit/widget/demo suite | 613 passed in the final CI run |
| Flutter analyzer | no issues |
| Local Web release | passed |
| Local macOS release | passed after Swift Package Manager migration |
| Read-only Management API integration | 9 passed against credential-free OrbStack services |
| Strict MkDocs build | passed |
| Native platform workflow | [run 29520314088](https://github.com/TVJunkie724/master-thesis/actions/runs/29520314088) passed Web, macOS, Windows, and Linux |

Review findings fixed during implementation:

1. Windows commonly exposes Python as `python`, while the entrypoint required
   `python3`; Python 3.9+ detection is now host-neutral and tested.
2. Shared Web/Desktop files imported direct OS process and filesystem APIs;
   native file writes now use conditional adapters and links use
   `url_launcher`.
3. Initial CI actions emitted Node 20 deprecation annotations; checkout now
   uses the pinned Node 24 action and the legacy indirect cache is disabled.
4. `file_saver` lacked current macOS package support; version `0.4.0` is used,
   CocoaPods integration was removed, and macOS plugins use Swift Package
   Manager.
5. The dependency update exposed Dio's new response-transformation timeout;
   both central error boundaries now map it consistently with regression tests.

The local universal macOS build still reports an upstream `objective_c`
framework-name warning while producing a valid release app. This is recorded as
a toolchain limitation, not hidden or treated as Windows/Linux evidence.
