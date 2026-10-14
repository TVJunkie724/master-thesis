# User-function data flow

```text
typed draft source + metadata
        |
        v
Management validation and Twin-owned digest
        |
        v
immutable calculation/deployment evidence
        |
        v
bounded operation package
        |
        v
Deployer revalidation + provider-owned wrapper
        |
        v
graph-selected runtime component
```

The portable Twin archive contains only allowlisted source and metadata. It
excludes credentials, Terraform state, deployment outputs and arbitrary
executables. Management owns the current draft source; the operation package
freezes the source digest selected for one deployment.

The Deployer rejects an unknown slot, changed digest, unsupported runtime,
unsafe path, secret-like content, invalid dependency shape or package/graph
mismatch. Provider adapters may add repository-owned wrapper code but may not
rewrite the user source silently.

There is no public artifact catalog, version history, ownership workflow,
legacy migration or provider-package upload. Git and exported Twin inputs
provide reproducibility; a deployed Twin is immutable.
