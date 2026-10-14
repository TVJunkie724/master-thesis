# Supported Platforms

The Flutter PoC is maintained for Web and desktop targets.

| Target | Contract | Evidence |
|---|---|---|
| Web | supported | release build and Flutter tests |
| macOS | supported | native release build on macOS |
| Windows | supported | native CI build on Windows |
| Linux | supported | native CI build with GTK toolchain |
| Android, iOS, Fuchsia | unsupported | rejected by the runtime contract |

All supported targets expose the same research workflow: Twin drafts, the fixed
architecture contract, cost calculation, deployment CloudConnections,
readiness/repair, immutable deployment operations, and evidence reads.

## Host requirements

All hosts require the repository-pinned Flutter toolchain, Python, and Git.
Docker is required only for the integrated backend stack. Demo mode does not
require Docker or provider access.

Build support is not distribution readiness. Signed installers, notarization,
store publication, platform certification, automatic updates, and production
support are outside the thesis scope.
