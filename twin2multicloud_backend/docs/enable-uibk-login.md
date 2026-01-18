# How to Enable UIBK Login

Step-by-step guide to enable UIBK Shibboleth SAML authentication.

---

## Prerequisites

- [ ] Access to UIBK ZID (IT department) contact
- [ ] Authority to sign legal agreements on behalf of your department
- [ ] Domain with HTTPS (e.g., `twin2multicloud.uibk.ac.at`)

---

## Phase 1: Generate SP Credentials (~30 min)

### Step 1.1: Generate Certificate and Private Key

```bash
# Generate a self-signed certificate valid for 1 year
openssl req -new -x509 -days 365 \
  -keyout sp-key.pem \
  -out sp-cert.pem \
  -subj "/CN=twin2multicloud.uibk.ac.at"

# View the certificate (optional)
openssl x509 -in sp-cert.pem -text -noout
```

### Step 1.2: Convert to Base64 for Environment Variables

```bash
# Convert certificate to single-line base64
cat sp-cert.pem | base64 -w0 > sp-cert.b64

# Convert private key to single-line base64
cat sp-key.pem | base64 -w0 > sp-key.b64

# Copy these values to your .env file
echo "SAML_SP_CERT=$(cat sp-cert.b64)"
echo "SAML_SP_KEY=$(cat sp-key.b64)"
```

---

## Phase 2: ACOnet Registration (1-2 weeks)

### Step 2.1: Get SP Metadata

Start the backend with SAML settings configured (can use dummy IdP cert for now):

```bash
# In .env
SAML_ENABLED=true
SAML_SP_ENTITY_ID=https://twin2multicloud.uibk.ac.at
SAML_ACS_URL=https://api.twin2multicloud.uibk.ac.at/auth/uibk/callback
SAML_SP_CERT=<your-base64-cert>
SAML_SP_KEY=<your-base64-key>
```

Then download metadata:
```bash
curl http://localhost:5005/auth/uibk/metadata > sp-metadata.xml
```

### Step 2.2: Download and Sign ACOnet Agreement

1. **Download SP Agreement**: 
   - Main website: **https://eduid.at** (verified working)
   - Look for "Teilnahme als SP" (Participate as SP) link
   - File needed: `ACOnet Identity Federation SP-Agreement v2-1.pdf`
   - If website links are broken, contact: **federation@aco.net**

2. Fill in organization details:
   - **Organization**: University of Innsbruck
   - **Department**: Your department/institute
   - **Technical Contact**: Your email
   - **Service Name**: Twin2MultiCloud
   
3. Get authorized signature (legally authorized person required)

4. Prepare a **Privacy Policy** statement for your service (required by ACOnet)

### Step 2.3: Submit to ACOnet

**Option A: Digital submission**
- Email to: **federation@aco.net**
- Attach digitally signed SP Agreement + SP Metadata XML

**Option B: Postal submission**
```
University of Vienna
Vienna University Computer Center
Department ACOnet & VIX
Universitätsstraße 7
1010 Vienna, Austria
```

> **Note:** Participation in ACOnet Identity Federation is **free of charge** for Service Providers.

### Step 2.4: Wait for Confirmation

ACOnet will:
1. Review your application
2. Add your SP to the federation metadata
3. Send confirmation with UIBK IdP metadata URL

---

## Phase 3: Configure Production Settings (~1 hour)

### Step 3.1: Get UIBK IdP Certificate

Download UIBK IdP metadata:
```bash
curl https://idp.uibk.ac.at/idp/shibboleth > idp-metadata.xml
```

Extract the certificate (look for `<ds:X509Certificate>` tag) and convert to base64.

### Step 3.2: Update Production Environment

```bash
# .env.production

# Enable SAML
SAML_ENABLED=true

# Your Service Provider
SAML_SP_ENTITY_ID=https://twin2multicloud.uibk.ac.at
SAML_ACS_URL=https://api.twin2multicloud.uibk.ac.at/auth/uibk/callback
SAML_SP_CERT=<your-base64-sp-cert>
SAML_SP_KEY=<your-base64-sp-key>

# UIBK Identity Provider
SAML_IDP_ENTITY_ID=https://idp.uibk.ac.at/idp/shibboleth
SAML_IDP_SSO_URL=https://idp.uibk.ac.at/idp/profile/SAML2/Redirect/SSO
SAML_IDP_CERT=<base64-encoded-idp-cert>

# Frontend redirect
FRONTEND_CALLBACK_URL=https://twin2multicloud.uibk.ac.at/auth/callback
```

### Step 3.3: Install python3-saml Dependencies

The `python3-saml` library requires `xmlsec`. Update your Dockerfile:

```dockerfile
# Add to Dockerfile
RUN apt-get update && apt-get install -y \
    libxmlsec1-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*
```

### Step 3.4: Run Database Migration

```bash
# If you have existing users in the database
docker exec -it <backend-container> python scripts/migrate_uibk_auth.py
```

---

## Phase 4: Enable Flutter UI (~10 min)

### Step 4.1: Uncomment UIBK Button

In `lib/screens/login_screen.dart`, find the commented UIBK button section and uncomment it:

```dart
// BEFORE: Commented out
// const SizedBox(height: 12),
// FilledButton.icon(
//   onPressed: () async { ... },
//   icon: const Icon(Icons.school),
//   label: const Text('Sign in with UIBK'),
//   ...
// ),

// AFTER: Uncommented
const SizedBox(height: 12),
FilledButton.icon(
  onPressed: () async {
    // TODO: implement production SAML flow
  },
  icon: const Icon(Icons.school),
  label: const Text('Sign in with UIBK'),
  style: FilledButton.styleFrom(
    backgroundColor: const Color(0xFF003366),
    foregroundColor: Colors.white,
    minimumSize: const Size(double.infinity, 48),
  ),
),
```

### Step 4.2: Implement Production Auth Flow

Replace the TODO with actual auth flow:

```dart
onPressed: () async {
  try {
    final response = await dio.get('/auth/uibk/login');
    final authUrl = response.data['auth_url'];
    await launchUrl(Uri.parse(authUrl), mode: LaunchMode.externalApplication);
  } catch (e) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('UIBK login failed: $e')),
    );
  }
},
```

---

## Phase 5: Testing (~2 hours)

### Step 5.1: Test with Mock IdP (Local Development)

Before connecting to real UIBK, test with SimpleSAMLphp:

```bash
docker run -d -p 8080:8080 \
  -e SIMPLESAMLPHP_SP_ENTITY_ID=http://localhost:5005 \
  -e SIMPLESAMLPHP_SP_ASSERTION_CONSUMER_SERVICE=http://localhost:5005/auth/uibk/callback \
  kristophjunge/test-saml-idp
```

### Step 5.2: Test Login Flow

1. Click "Sign in with UIBK"
2. Should redirect to IdP login page
3. Enter test credentials
4. Should redirect back with JWT token
5. Should show dashboard

### Step 5.3: Test Account Linking

1. Create account via Google
2. Log out
3. Log in via UIBK with same email
4. Verify accounts are linked (check database)

### Step 5.4: Test with Real UIBK IdP

After ACOnet approval:
1. Deploy to production server
2. Test with real UIBK credentials
3. Verify all user attributes are received

---

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| 503 "UIBK login not available" | `SAML_ENABLED=false` | Set to `true` in `.env` |
| 503 "SAML library not installed" | Missing python3-saml | Install: `pip install python3-saml` |
| "Signature validation failed" | Wrong IdP certificate | Re-download from IdP metadata |
| "Missing 'mail' attribute" | IdP not releasing email | Check SP metadata attribute requirements |
| Redirect loop | Wrong ACS URL | Verify `SAML_ACS_URL` matches SP metadata |

---

## Quick Reference: All Environment Variables

```bash
# Required for UIBK login
SAML_ENABLED=true
SAML_SP_ENTITY_ID=https://your-domain.uibk.ac.at
SAML_ACS_URL=https://api.your-domain.uibk.ac.at/auth/uibk/callback
SAML_SP_CERT=<base64>
SAML_SP_KEY=<base64>
SAML_IDP_ENTITY_ID=https://idp.uibk.ac.at/idp/shibboleth
SAML_IDP_SSO_URL=https://idp.uibk.ac.at/idp/profile/SAML2/Redirect/SSO
SAML_IDP_CERT=<base64>
FRONTEND_CALLBACK_URL=https://your-domain.uibk.ac.at/auth/callback
```

---

## Timeline Summary

| Phase | Duration | Blocking? |
|-------|----------|-----------|
| Generate credentials | 30 min | No |
| ACOnet registration | 1-2 weeks | **Yes** |
| Configure production | 1 hour | No |
| Enable Flutter UI | 10 min | No |
| Testing | 2 hours | No |

**Total hands-on time:** ~4 hours  
**Total wall-clock time:** ~2 weeks (due to ACOnet registration)
