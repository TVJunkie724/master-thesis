# Implementation Plan: Local Runtime Secret Bootstrap

**Status:** Implemented, twice reviewed, and verified.

## 0. Git Branch

- **Branch:** `codex/local-secret-bootstrap`
- **Base:** `master` at `ef66456`
- **Merge strategy:** merge commit; no rebase
- **GitHub issue:** [#9](https://github.com/TVJunkie724/master-thesis/issues/9)

## 1. Summary

Replace the tracked Compose development JWT/encryption defaults with durable,
random local runtime secrets. `thesis.sh` becomes the only automatic bootstrap
entry point. It creates or validates ignored host secret files before any
Management API container starts. Compose mounts those files read-only through
its native secret mechanism, and Pydantic reads them from `/run/secrets`.

Automatic generation is strictly local. Production keeps accepting explicit
secret environment/file sources but never generates keys. Existing encrypted
CloudConnections must never become unreadable because a missing key was
silently replaced.

## 2. Security And Data-Flow Contract

```text
fresh local clone
    |
    v
./thesis.sh setup | up | test backend | test frontend-integration
    |
    v
scripts/bootstrap_local_runtime_secrets.py
    |-- validate .secrets/runtime directory (real directory, owner-only)
    |-- preserve and validate existing keys
    |-- import explicitly supplied env keys, when present
    |-- reject generation when encrypted DB records already exist
    `-- otherwise atomically create random JWT + encryption keys
             |
             v
      host files 0600, parent 0700
             |
             v
      Docker Compose secrets (read-only, host mode 0600)
             |
             v
      /run/secrets/JWT_SECRET_KEY
      /run/secrets/ENCRYPTION_KEY
             |
             v
      Pydantic Settings -> JWT signer / scoped credential encryption
```

No command may print secret values. No secret value may enter Git, generated
Flutter config, logs, command arguments, or API responses.

## 3. Files And Responsibilities

| File | Change | Binding responsibility |
|---|---|---|
| `scripts/bootstrap_local_runtime_secrets.py` | New | Dependency-free, atomic, idempotent host secret bootstrap and validation |
| `scripts/tests/test_bootstrap_local_runtime_secrets.py` | New | Filesystem, migration guard, permission, symlink, and idempotency tests |
| `thesis.sh` | Modify | Invoke bootstrap before every local command that can start/run Management API |
| `compose.yaml` | Modify | Remove hardcoded secret defaults; mount named Compose secrets read-only |
| `twin2multicloud_backend/src/config.py` | Modify | Read `/run/secrets`; require valid non-empty keys in every runtime; production remains fail-closed |
| `twin2multicloud_backend/tests/test_security_config.py` | Modify | Secret-file, precedence, missing/weak, production, and placeholder rejection tests |
| `twin2multicloud_backend/.env.example` | Modify | Document explicit environment source and Compose file-secret source without sample secrets |
| `HANDBOOK.md` | Modify | Explain first-start behavior, paths, backup/rotation warning, and production boundary |
| `docs-site/docs/architecture/refactoring-roadmap.md` | Modify | Mark #9 complete and update Phase 4 sequence |

## 4. Bootstrap Contract

The bootstrap utility must:

1. Accept explicit `--secrets-dir` and `--database` paths.
2. Create only `JWT_SECRET_KEY` and `ENCRYPTION_KEY` in the selected directory.
3. Use cryptographically secure randomness from Python's `secrets` module.
4. Generate a JWT key with at least 256 bits and a URL-safe base64 encryption
   key representing exactly 32 random bytes.
5. Normalize the real directory to exactly `0700` and regular files to exactly
   `0600`; owner read/write/execute access is required for reliable operation,
   while every group/other permission is removed.
6. Use exclusive, no-follow, atomic creation and `fsync`; reject symlinks,
   hardlinks, foreign-owned/non-regular files, control characters, empty
   values, duplicate values, and malformed encryption keys.
7. Preserve valid existing values byte-for-byte.
8. Persist explicitly supplied `JWT_SECRET_KEY` / `ENCRYPTION_KEY` values when
   the corresponding file is absent, after applying the same validation.
9. Query only the local SQLite `cloud_connections` row count. If encrypted rows
   exist and `ENCRYPTION_KEY` is neither already persisted nor explicitly
   supplied, fail before creating either key.
10. Roll back files created by the current invocation when the pair cannot be
    completed, so partial bootstrap cannot become the next run's source.
11. Emit only path/status metadata, never values or fingerprints.

## 5. Runtime Configuration Contract

- `Settings` uses `/run/secrets` as an optional Pydantic secrets directory.
- Explicit environment variables retain higher Pydantic precedence for
  non-Compose production deployments. Standard Compose does not forward those
  values; the local bootstrap imports them into the mounted files first.
- `JWT_SECRET_KEY` and `ENCRYPTION_KEY` are required in development, test, and
  production and must each contain at least 32 characters.
- Keys must differ.
- Known repository placeholder/development values are rejected in every mode.
- Production still rejects debug, dev auth, test endpoints, and seed data.
- The application performs no key generation or file writes at import/startup.

## 6. Compose And Entrypoint Contract

- `compose.yaml` defines named file-backed secrets and mounts them only into the
  Management API as `JWT_SECRET_KEY` and `ENCRYPTION_KEY`. Local Compose uses a
  read-only bind mount and preserves the host `0600` mode; no unsupported
  container-mode declaration is used.
- The two hardcoded environment defaults are removed.
- Secret file paths are configurable through `THESIS_RUNTIME_SECRETS_DIR` while
  defaulting to `.secrets/runtime`.
- `thesis.sh` runs bootstrap before `up`, `setup`, `test backend`, and
  `test frontend-integration`.
- `flutter`, `demo`, `config`, `docs`, `latex`, `status`, `logs`, and `down` do
  not generate keys because they do not require a new Management API runtime.
- `thesis.sh` gains an explicit `secrets` command for deterministic setup and
  diagnostics without starting containers.
- Existing values are never rotated automatically. Rotation remains an
  explicit future security operation because encrypted database payloads must
  be re-encrypted transactionally.

## 7. Compatibility And Failure Behavior

| Condition | Required result |
|---|---|
| Fresh clone, no DB rows, no files | Generate both keys and continue |
| Both valid files exist | Preserve both and continue |
| Explicit env values, files absent | Validate, persist, continue |
| Existing encrypted rows, encryption file absent, env absent | Fail before mutation with recovery guidance |
| One existing file invalid | Fail; do not replace it silently |
| One generated file followed by second-file failure | Remove only files created by this invocation |
| Symlink/non-regular target | Fail without following or modifying target |
| Production process without explicit keys | Pydantic startup validation fails |
| Known development placeholder | Startup/bootstrap validation fails |

The database guard intentionally reads only row counts and never credential
payloads. Non-SQLite production databases are outside the local bootstrap and
must use explicitly provisioned secrets.

## 8. Error Handling And Observability

- Bootstrap errors use one public exception type and concise actionable stderr.
- Values, hashes, lengths tied to user-provided secrets, and file contents are
  excluded from output.
- `thesis.sh` propagates a non-zero status and does not invoke Compose after a
  bootstrap failure.
- Successful output distinguishes `created`, `imported`, and `preserved` only.
- Backend configuration errors name the invalid setting but never its value.

## 9. Documentation

`HANDBOOK.md` must explain:

- `./thesis.sh setup` and `./thesis.sh secrets` behavior;
- ignored local paths and permissions;
- why deleting `ENCRYPTION_KEY` can make stored CloudConnections unreadable;
- how explicit environment values are imported for local migration;
- why Production must use an operator-provisioned secret source;
- that cloud admin credentials remain separate and are never handled here.

No secret-management theory page or speculative vault integration is added in
this slice; broader production controls remain in #8.

## 10. Implementation Order

1. Add and test the standalone bootstrap utility.
2. Harden `Settings` and its security tests.
3. Replace Compose environment defaults with read-only secrets.
4. Wire `thesis.sh` commands and add the explicit `secrets` command.
5. Update examples, handbook, roadmap, and issue evidence.
6. Run two independent reviews: security/failure atomicity, then integration
   compatibility and documentation consistency.

Every step is mandatory and may not be skipped.

## 11. Test Plan

### Unit and filesystem tests

- Fresh generation creates two valid, distinct values with exact permissions.
- Second execution is byte-for-byte idempotent.
- Explicit environment values are imported without disclosure.
- Existing encrypted row guard fails before mutation.
- Existing invalid/weak/placeholder/duplicate values fail closed.
- Symlink, hardlink, directory target, control character, and malformed base64
  inputs fail.
- A simulated second-file write failure rolls back first-file creation.
- Existing directory/file permissions are normalized to `0700`/`0600`.

### Backend configuration tests

- Environment values and `/run/secrets`-equivalent test directory load correctly.
- Environment values override file secrets.
- Missing, weak, duplicate, and placeholder keys fail in development and production.
- Existing production capability checks remain green.

### Compose and entrypoint tests

- `docker compose config` contains no hardcoded JWT/encryption value.
- Generated temporary files satisfy `docker compose config` path interpolation.
- `./thesis.sh secrets` succeeds twice without changing values.
- `./thesis.sh test backend` passes using Compose-mounted secrets.
- Credential-free `./thesis.sh up --no-flutter` reaches Management API health.

### Regression gates

- Complete Management API suite excluding `tests/e2e`.
- Root script unit suite.
- `bandit -r twin2multicloud_backend/src twin2multicloud_backend/scripts`.
- `git diff --check` and a secret-value/placeholder guard scan.
- No live-cloud E2E or resource mutation.

### Final evidence

- Complete Management API suite: **659 passed**.
- Root script/architecture suite: **25 passed**, including **13** dedicated
  bootstrap filesystem and migration-guard tests.
- Focused runtime settings/crypto suite: **24 passed**.
- `mkdocs build --strict`: passed.
- Bandit for Management API sources/scripts and the host bootstrap: passed.
- Real OrbStack startup and health check with read-only `0600` Compose secret
  mounts: passed.
- Entrypoint invocation from `/tmp`, Compose config, Git-ignore, and generated
  value leak guards: passed.
- No live-cloud E2E or resource mutation was executed.

## 12. Definition Of Done

- [x] No tracked Compose JWT/encryption defaults remain.
- [x] Fresh local setup creates durable cryptographically random keys.
- [x] Key directory/file permissions and no-follow atomic writes are verified.
- [x] Existing encrypted local data cannot be orphaned silently.
- [x] Compose mounts keys read-only and Management API reads them successfully.
- [x] Missing/weak/duplicate/placeholder keys fail closed in every environment.
- [x] Production never auto-generates secrets.
- [x] All local Management API start/test entry points bootstrap consistently.
- [x] Secret values never appear in output, docs, Flutter config, or Git diff.
- [x] Focused and complete backend tests pass.
- [x] Security scanner and Compose validation pass.
- [x] Handbook, roadmap, and #9 contain final evidence.
- [x] Two reviews report zero unresolved findings.
