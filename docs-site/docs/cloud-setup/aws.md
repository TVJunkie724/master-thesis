# AWS Setup

## Tools And Identity

The bootstrap artifact is `bootstrap/aws/bootstrap_deployment_identity.sh` and requires
the AWS CLI authenticated as an operator allowed to manage the target IAM identity and
policy. Administrator material is consumed by the CLI session, not by the script as an
argument and not by the Management API database.

## Workflow

```bash
bash bootstrap/aws/bootstrap_deployment_identity.sh --help
# run the generated/dry-run command from the Management API bootstrap plan
# add --apply only after reviewing account, region, identity, and policy
```

The output auth type is `access_key`. Import it through Cloud Accounts as a deployment
CloudConnection and retain `permission_set_version=thesis-demo-v1` metadata.

Existing access keys are not rotated implicitly. Rotation requires the explicit
`--rotate-access-keys` guard and may revoke the old key; plan consumer cutover first.

## Pricing Versus Deployment

AWS pricing retrieval and infrastructure deployment have different API surfaces. The
pricing policy reference under `2-twin2clouds/docs/references` is separate from the
Deployer baseline under `3-cloud-deployer/docs/references`. Do not merge them into an
unreviewed broad role solely for convenience.

## Verification Status

Static policy syntax, permission inventory, preflight behavior, and mocked provider
tests are implemented. Final least-privilege completeness requires supervised refresh,
deploy, verification, and destroy in the intended account/regions.
