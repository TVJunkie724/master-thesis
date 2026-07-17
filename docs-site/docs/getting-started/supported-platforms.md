# Supported Platforms

Twin2MultiCloud is a Web and desktop application. The application-wide support
contract is:

| Target | Status | Build evidence | Local entrypoint |
|---|---|---|---|
| Web | Supported | Web release build on Linux CI | `./thesis.sh flutter --device chrome` |
| macOS | Supported | Native macOS release build | `./thesis.sh flutter` on macOS |
| Windows | Supported | Native Windows release build | `./thesis.sh flutter` in Git Bash on Windows |
| Linux | Supported | Native Linux release build | `./thesis.sh flutter` on Linux |
| Android | Unsupported | Rejected by the runtime contract | None |
| iOS | Unsupported | Rejected by the runtime contract | None |
| Fuchsia | Unsupported | Rejected by the runtime contract | None |

The contract applies to every application feature, including sign-in,
configuration, cloud accounts, pricing review, deployment, file selection,
downloads, the offline demo, and diagnostics.

## What Supported Means

Supported targets have a tracked Flutter runner, a typed runtime
classification, unit-test coverage, and an automated release build on an
appropriate native runner. The quality workflow builds all four targets after
changes to Flutter, its entrypoint, or the workflow itself.

```text
Flutter source
  |-- Web build      (Ubuntu)
  |-- macOS build    (macOS)
  |-- Windows build  (Windows)
  `-- Linux build    (Ubuntu + GTK toolchain)
```

The local `./thesis.sh test frontend` command builds Web and the desktop target
native to the current host. A macOS machine cannot be used as Windows or Linux
build evidence; those guarantees come from their native CI jobs.

## Host Requirements

All hosts require Flutter `3.44.0`, Python 3.9 or newer, Git, and Docker when
the real backend stack is used. The entrypoint accepts Python as `python3` or
`python`. Demo mode does not require Docker.

| Host | Additional requirement |
|---|---|
| macOS | Xcode command-line and macOS desktop tooling configured for Flutter |
| Windows | Visual Studio with Desktop development with C++, Docker Desktop, and Git Bash for `thesis.sh` |
| Linux | Clang, CMake, Ninja, pkg-config, GTK 3 development headers, and a compatible Docker engine |
| Web | A supported Flutter browser device such as Chrome |

Use `--device` or `THESIS_FLUTTER_DEVICE` only to override the detected native
desktop, for example to run Web on a desktop host. Unknown hosts fail closed and
must provide an explicit Flutter device.

## Deliberate Boundary

Build support is not the same as distribution readiness. The current project
does not claim signed Windows installers, notarized macOS packages, Linux
distribution packages, store publication, or platform certification. These are
release-engineering concerns outside the current application runtime.
