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

In **Settings → Cloud access → AWS** choose one path:

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

## First Grafana sign-in (PoC administrator)

The PoC operator may also administer the AWS account. Deployment credentials
and personal dashboard sign-in are separate: an IAM access key is not an
Identity Center password. The dashboard user needs only Grafana **Viewer**
access; the deployment binds the selected identity to the workspace.

Before a paid Grafana run, prepare the intended sign-in once:

1. Open **IAM Identity Center** in its configured primary Region and choose
   **Users**. Select the username that will be shown on the Twin's L5 access card.
2. If the password is unknown or has not been set, choose **Reset password**.
   Send setup instructions only if that user's email address is reachable;
   otherwise choose **Generate a one-time password** and use it yourself at
   the displayed AWS access portal URL. Set your personal password there.
3. If AWS requires MFA, complete **Register an MFA device**, for example with
   an authenticator app. Follow the sign-in prompts on subsequent logins.
   Keep the existing organization policy; no MFA exemption is needed for the PoC.
4. After deployment, use **Twin overview → L5 → Open** and sign in with that
   same Identity Center user. Your AWS console administrator session does not
   automatically sign this user into Grafana.

An access portal with no assigned application before deployment or after
Destroy is expected. It does not prove the dashboard is deployed. Reuse the
existing identity on later runs; do not create a new human user for each test.
Never copy passwords, MFA setup keys or QR codes into logs, screenshots or
repository files. See AWS's [password setup and reset instructions](https://docs.aws.amazon.com/singlesignon/latest/userguide/reset-password-for-user.html)
and [MFA registration instructions](https://docs.aws.amazon.com/singlesignon/latest/userguide/user-device-registration.html).

## Cleanup and revocation

Twin Destroy removes Twin-owned resources and is followed by residual inventory
inspection. It does not remove the IAM identity, access key, account-level
settings, or shared service prerequisites. After the final run, unbind and delete
the CloudConnection, deactivate/delete the access key in AWS, and review the
identity for residual permissions.

See the official [AWS references](provider-links.md#aws).
