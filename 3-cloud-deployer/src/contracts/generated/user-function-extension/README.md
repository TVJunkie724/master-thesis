# User-Function Extension Contract

This directory is the canonical repository source for the provider-neutral
user-function extension boundary required by Phase 8.

Version 1 supports Python 3.11 domain source with a single top-level
`process` entrypoint, deterministic hashed `requirements.lock`, typed
non-secret configuration, immutable artifacts, platform-owned provider
wrappers, and one canonical runtime envelope.

The user owns only approved source, dependencies, declared capabilities, and
fields marked `user_editable` by the registered slot. The platform owns
handlers, wrappers, provider resource identities, topology bindings,
permissions, runtime policy, observability, retries, limits, and
infrastructure references.

Canonical files are synchronized byte-for-byte into the Management API and
Deployer generated contract directories by
`scripts/sync_user_function_extension_contracts.py`. Generated copies must not
be edited directly.

Version 1 deliberately rejects user-managed secret values and references.
Provider-managed extension secrets are separate future work.
