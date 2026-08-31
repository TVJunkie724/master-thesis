# AWS Setup

## Prerequisites

- Use an existing isolated AWS account with billing available.
- Never use the root user or root access keys.
- Create one non-root programmatic identity for this supervised PoC. The current
  import contract accepts an IAM access-key CSV; temporary role credentials are
  not yet a supported CloudConnection input.
- Limit the identity to the services and Regions in the resolved Six-layer graph.
  The readiness check reports the exact missing actions before deployment.

AWS recommends temporary credentials in general. The long-lived access key is a
bounded PoC compatibility choice, not a production identity pattern. Store it
securely and revoke it after the evaluation.

## Enter or import

In **Settings → Deployment administrators → AWS** choose one path:

- **Enter manually:** access key ID, secret access key, primary Region, optional
  IAM Identity Center Region, and an optional session token.
- **Import CSV:** the standard AWS access-key CSV. Account ID and IAM Identity
  Center Region remain typed metadata; file contents are never previewed.

Do not paste credentials into project configuration, evidence, screenshots,
issues, logs, or documentation.

## Validation checkpoints

Before binding the connection, confirm that readiness reports:

1. the expected caller and isolated account;
2. the configured Region and regional STS endpoint;
3. all graph-required service actions and quota/capacity headroom;
4. IAM Identity Center primary-Region readiness when the selected path needs it;
5. no organization SCP, Marketplace, legal, or quota blocker.

Validation is read-only. A failure does not authorize Twin2MultiCloud to change
IAM or organization policy.

## Cleanup and revocation

Twin Destroy removes Twin-owned resources and is followed by residual inventory
inspection. It does not remove the IAM identity, access key, account-level
settings, or shared service prerequisites. After the final run, unbind and delete
the CloudConnection, deactivate/delete the access key in AWS, and review the
identity for residual permissions.

See the official [AWS references](provider-links.md#aws).
