# Azure Setup

## Tools And Scope

`bootstrap/azure/bootstrap_deployment_identity.sh` uses Azure CLI authentication to
create or update a constrained service principal and role assignment. Confirm tenant,
subscription, and intended scope before applying.

The generated CloudConnection auth type is `service_principal` and includes tenant,
subscription, client ID, and client secret in the encrypted payload. The API exposes
scope metadata but never the secret.

## Workflow

```bash
bash bootstrap/azure/bootstrap_deployment_identity.sh --help
# dry-run/review first; use --apply deliberately
```

Existing client secrets are not multiplied silently. Rotation requires
`--rotate-client-secret` and should be coordinated with replacement/import/validation.

## Pricing Versus Deployment

Azure retail pricing APIs can provide public catalog data for many scenarios, while
deployment and some account/scope checks require tenant/subscription credentials. The
application records the requested region, source endpoint, selected catalog identities,
and mapping version so pricing evidence remains auditable; no Azure credential is used
for this public refresh. Do not infer deployment authorization from successful public
pricing access.

Role/policy references and the setup helper under `3-cloud-deployer/docs/references`
are baseline inputs. Azure Functions hosting model, diagnostic settings, Digital Twins,
Grafana, and role-assignment behavior may add scope-specific requirements.

## Verification Status

The baseline and mocked preflight are implemented. Known Azure provider gaps and
conflict conditions remain linked from the refactoring roadmap. Final least privilege
requires supervised target-subscription evidence.
