# AWS Setup

Use an existing isolated AWS account and a non-root deployment administrator
access key. Import the standard access-key CSV or enter the values in the
write-only form, then verify the returned account/ARN and selected region.

Graph readiness checks only the services, permissions, quotas and identity
requirements needed by the selected Six-layer deployment. AWS IAM Identity
Center primary Region and the regional STS endpoint are separate prerequisites
when the chosen access/federation path needs them.

Account creation, payment/billing recovery, quota approval, organization SCP
changes, Marketplace/legal acceptance, and credential rotation/revocation are
manual. There is no AWS pricing credential or TwinMaker account-plan workflow.
