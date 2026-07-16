# Enable UIBK Login

Use this checklist only after reading `uibk-authentication.md` and the canonical
docs-site authentication page. It deliberately does not contain placeholder
URLs, certificates, or a development bypass.

## 1. Establish Institutional Values

- obtain the approved public HTTPS Management API domain;
- agree the exact SP entity ID and ACS URL with UIBK/ACOnet;
- establish SP key ownership, secret provisioning, rotation, and expiry alerts;
- obtain authoritative UIBK IdP metadata and required attribute release;
- obtain an approved test identity and registration confirmation.

Track this evidence in GitHub issue
`#49 Document and resolve UIBK login prerequisites`.

## 2. Provision Secrets And Configuration

Set the complete `SAML_*` tuple from `.env.example` in the deployment secret
boundary. Do not add it to Compose source, Flutter defines, tracked JSON, or
shell history. Production also requires strong JWT/encryption keys, HTTPS,
explicit HTTPS CORS origins, and Redis-backed authentication/credential rate
limits.

Start the Management API. It must fail startup when SAML is incomplete or its
runtime dependency is unavailable.

## 3. Register Exact Metadata

```bash
curl --fail --silent --show-error \
  https://<management-api-host>/auth/uibk/metadata \
  --output sp-metadata.xml
```

Review and submit this generated metadata through the approved institutional
process. The configured entity ID, ACS URL, and certificate must exactly match
the registered values.

## 4. Verify Capability And Safe Failure

```bash
curl --fail --silent --show-error \
  https://<management-api-host>/auth/providers
```

UIBK must be `enabled: true` only after complete configuration. Before a live
test, verify that expired/replayed transactions, incorrect `InResponseTo`, bad
signatures, missing NameID/mail, and disabled SAML all fail without exposing
assertion content.

## 5. Run Supervised Live Evidence

1. initiate UIBK from Flutter;
2. authenticate at the real IdP;
3. verify the no-secret callback page;
4. verify one successful Flutter session exchange;
5. verify replay fails;
6. log out and verify the JWT is revoked server-side;
7. inspect secret-free authentication events and request correlation;
8. confirm edge/access logs do not retain SAML assertions or callback query
   values.

Do not close the activation issue based only on unit tests or mock-IdP output.
