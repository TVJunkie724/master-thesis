# Cloud Setup

Cloud access is deliberately narrow for this thesis PoC. Start with an existing,
billing-enabled and isolated provider scope. Twin2MultiCloud stores the supplied
credential bundle encrypted, validates it read-only, and uses it only for a
confirmed deployment, verification, Destroy, or bounded preparation operation.

| Provider | Stored authority | Accepted input |
|---|---:|---|
| AWS | one deployment identity | access-key CSV or typed fields |
| Azure | one deployment principal plus one preparation principal in one bundle | typed fields, one deployment-principal JSON plus typed preparation fields, or one complete allowlisted compatibility JSON |
| Google Cloud | one deployment service account | service-account JSON or typed fields |

## Common lifecycle

1. Prepare the provider identity or identities outside Twin2MultiCloud.
2. In **Settings → Cloud access**, open the provider setup guide.
3. Enter or import the credential material through the write-only form.
4. Validate the returned identity, target scope, effective permissions, Regions,
   quotas, and provider prerequisites before binding the connection to a Twin.
5. Review every graph-derived preparation plan and explicitly confirm it.
6. Deploy only from the immutable plan, verify the run, Destroy immediately, and
   inspect residual inventory.
7. After the evaluation, delete the unbound CloudConnection and revoke or delete
   the provider-side credential manually.

Twin2MultiCloud does not create accounts, subscriptions, or projects; repair
billing; approve quota increases; override organization policy; accept legal or
preview terms; grant Microsoft Graph admin consent; or manage credential
rotation. Those conditions are reported as external blockers.

Continue with [AWS](aws.md), [Azure](azure.md), or
[Google Cloud](gcp.md). Current provider documentation is collected under
[Provider Links](provider-links.md).
