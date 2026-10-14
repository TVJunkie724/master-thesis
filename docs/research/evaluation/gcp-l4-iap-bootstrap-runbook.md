# GCP L4 IAP bootstrap runbook

Status: approved PoC design; not executed. A separate explicit cloud-mutation
approval is required before following this runbook.

## Purpose and boundary

The GCP L4 surface is the existing read-only Cloud Run Twin Explorer protected
by direct Identity-Aware Proxy (IAP). The evaluation project has no Google
Cloud organization, so its first L4 run needs one project-level custom OAuth
configuration. The Google Cloud console creates that configuration; the PoC
does not implement OAuth, issue tokens, introduce a load balancer, or add an
authentication service.

The bootstrap is intentionally deferred until an explicitly approved GCP
scenario has created the actual Twin Explorer. It then runs after L1--L3 and
Event Layer verification and immediately before the first L4 check. This keeps
the bootstrap bound to the evaluated resource and avoids a placeholder
deployment.

## Expected provider changes

Exactly these persistent project-level changes are expected:

1. minimal Google Auth Platform branding and an `External` audience;
2. one console-generated Web OAuth client configured for IAP; and
3. the corresponding project-level IAP OAuth setting and redirect URI.

The procedure must not create another Cloud Run service, load balancer,
network, compute resource, or additional IAM binding. Terraform already grants
the IAP service agent `roles/run.invoker` on the Twin Explorer and grants the
selected platform user `roles/iap.httpsResourceAccessor`.

## Preconditions

Proceed only when all of the following hold:

- the exact GCP scenario, revision, resource names, numerical scenario cap,
  runtime limit, timer, operator, and cleanup owner have been reviewed;
- the scenario has separate explicit Apply approval and the expected Twin
  Explorer now exists;
- L1--L3 and Event Layer verification has passed for that scenario;
- the operator is signed in to the intended project and already has the
  Cloud Run Admin, IAP Policy Admin, IAP Settings Admin, and OAuth Config
  Editor permissions required for this console path; and
- current IAP behavior and pricing have been rechecked against the official
  Google Cloud documentation.

If a role is missing, stop. This runbook does not authorize granting a role.

## Supervised console procedure

1. Start the five-minute bootstrap timer and record only the scenario ID,
   revision, start time, and secret-free pre-state.
2. In Cloud Run, open the scenario's Twin Explorer, select its security/IAP
   configuration, and continue to IAP when prompted.
3. Configure the minimal consent screen with an `External` audience. Do not
   add a logo, custom domain, optional scope, or verification workflow.
4. For the IAP OAuth configuration, choose the console action to auto-generate
   credentials and save it. Do not manually create another client.
5. Do not download, copy, display, log, or export the client ID or client
   secret. Do not add either value to Terraform, repository files, evidence,
   shell history, or application configuration.
6. Do not change IAM. If the existing Terraform-managed bindings are
   insufficient, record the blocker and stop.

Warn at minute three. If setup and the bounded verification are not complete
by minute five, stop, roll back the OAuth configuration, and immediately
Destroy the active scenario.

## Cost and abort boundary

The expected and technical upper bound for the direct incremental IAP
bootstrap cost is **USD 0.00**. The already reviewed scenario cap separately
covers the short lifetime of its existing Cloud Run resource.

Abort before confirmation if the console requests a paid Chrome Enterprise
feature, load balancer, additional compute or networking resource, verification
fee, subscription, or any other billable addition. An unexpected minimum or
non-prorated charge also blocks the run; it does not raise the cap.

## Bounded verification

The bootstrap passes only when all of the following are observed:

1. an unauthenticated private-browser request is redirected to Google sign-in
   and cannot read the Twin Explorer;
2. the Terraform-selected platform user can sign in and open the read-only
   Twin Explorer;
3. one bounded read of model, Twin/current state, and relationship data works;
4. no write action and no raw-telemetry access is exposed; and
5. no credential value appears in logs, state, screenshots, or evidence.

Record only the scenario ID, revision, timestamps, bootstrap mode
`iap_console_auto_generated_custom_oauth`, redirect result, authorized and
unauthorized outcomes, bounded-read result, duration, USD 0.00 incremental
cost cap, and cleanup state. Do not record user email addresses, client IDs,
client secrets, credential paths, or provider resource identifiers.

## Cleanup and residual inventory

Normal scenario cleanup remains immediate Terraform Destroy followed by the
typed residual-inventory check. Until the last required GCP L4 scenario, the
project-level OAuth bootstrap is listed separately as a known, non-workload
evaluation prerequisite; it is not misclassified as a leaked Twin resource.

After the final GCP L4 evaluation:

1. remove the custom OAuth configuration from IAP and delete its
   console-generated credentials;
2. verify that no active generated OAuth client or custom IAP OAuth setting
   remains; and
3. record any provider-retained, non-billable branding/audience metadata as a
   project-level residual for final project teardown.

On setup or verification failure, perform the same OAuth rollback immediately,
then Destroy the current scenario and reconcile the residual inventory before
any further evaluation.

## Research-question evidence

- **RQ1:** count the manual bootstrap as an operational step and measure its
  duration separately from Apply and L4 verification.
- **RQ2:** use the authenticated, bounded read-only browser result as the GCP
  L4 functional-comparability observation.
- **RQ3:** record the direct incremental bootstrap cap as USD 0.00 while keeping
  the scenario's runtime and observed provider cost separate.

## Authoritative references

- [IAP for Cloud Run](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)
- [Configure a custom OAuth client for IAP](https://docs.cloud.google.com/iap/docs/custom-oauth-configuration)
- [Google-managed OAuth client](https://docs.cloud.google.com/iap/docs/managed-oauth-client)
- [IAP pricing](https://cloud.google.com/iap/pricing)
