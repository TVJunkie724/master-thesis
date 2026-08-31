# Twin2MultiCloud Flutter Client

The Flutter application presents the thesis research workflow and calls only
the Management API.

## Safe start

Offline deterministic demo:

```bash
./thesis.sh demo --setup
```

Integrated local stack:

```bash
./thesis.sh up --setup
```

Neither path contacts a cloud provider by default.

## Current workflow

1. Create, import or duplicate a Twin draft.
2. Configure typed workload, state/simulator data and bounded user functions.
3. Read the one canonical `six-layer-eventing@1` contract.
4. Calculate and review cost, exclusions, assumptions and immutable graph.
5. Select named deployment CloudConnections required by the result.
6. Run readiness, confirm bounded preparation, or follow repair guidance.
7. Confirm Deploy, follow persisted progress/SSE replay and verify telemetry.
8. Open provider-owned L4/L5 access links.
9. Confirm Destroy and inspect cleanup evidence.

The **Twin experiments** inventory is intentionally a start-or-resume surface:
`New Twin` is the only primary action, every row has one state-specific
continuation, and Duplicate/Export/Delete remain in a secondary overflow.
There are no filters, analytics, provider columns or bulk operations.

There is no profile/objective selector, pricing administration workspace,
generic deployment-project UI, embedded dashboard administration, or in-place
infrastructure update.

## State architecture

Riverpod composes dependencies and simple global state. Feature-scoped BLoCs
own multi-step commands, retries, stale-response protection, operation replay,
and one-time secret consumption. Each mutable concern has one owner.

CloudConnection entry/import is write-only. Flutter stores only returned
non-secret metadata. A service-local one-time Viewer value may enter transient
state and is discarded after use; provider administrator secrets never do.
The **Cloud access** screen is import-first and keeps manual entry as a fallback.
Azure file selection accepts a standard deployment service-principal JSON or
the complete allowlisted Azure compatibility bundle, prefills known fields
locally and uploads only normalized deployment-principal fields.

## Runtime configuration

`config/dev.example.json` and `config/production.example.json` document the
supported runtime shape. Networked modes require the local PoC profile bearer;
missing or invalid mode/origin/token values fail bootstrap. The dormant login
screen is deliberately not routed. Demo mode uses a tracked secret-free
configuration and in-memory adapters behind the same interfaces.

## Verification

```bash
cd twin2multicloud_flutter
flutter analyze
flutter test
python3 scripts/check_flutter_architecture.py
flutter build web --release
```

Use the native release build on the current desktop host as an additional
gate. These checks prove client behavior, not live provider deployment.
