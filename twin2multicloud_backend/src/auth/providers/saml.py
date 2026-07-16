"""
UIBK Shibboleth SAML Provider

This module implements SAML Service Provider (SP) functionality for 
authenticating users via the University of Innsbruck (UIBK) Identity Provider.

The user logs in with their UIBK username/password at the IdP.
The IdP then sends back user attributes (email, name, etc.) from the 
university's LDAP directory - the user doesn't enter email manually.

URL Configuration:
- LOCAL DEV: Use http://localhost:5005/auth/uibk/callback with a MOCK SAML IdP
- PRODUCTION: Must use HTTPS URL registered with ACOnet 
  (e.g., https://api.twin2multicloud.uibk.ac.at/auth/uibk/callback)

Note: The real UIBK IdP will REJECT localhost URLs - registration with ACOnet is required!
"""

import re
from urllib.parse import urlparse
from typing import Optional

# Note: python3-saml requires xmlsec library. If not installed, these imports will fail.
# For development without SAML, the SAML_ENABLED flag can be set to False.
try:
    from onelogin.saml2.auth import OneLogin_Saml2_Auth
    from onelogin.saml2.utils import OneLogin_Saml2_Utils
    SAML_AVAILABLE = True
except ImportError:
    SAML_AVAILABLE = False
    OneLogin_Saml2_Auth = None
    OneLogin_Saml2_Utils = None

from src.auth.providers.base import ProviderAuthorization, VerifiedExternalIdentity
from src.config import settings


class UIBKSAMLProvider:
    """
    SAML Service Provider for UIBK Shibboleth integration.
    
    Unlike OAuth, SAML uses XML-based assertions instead of tokens.
    This provider handles the SP-initiated SSO flow.
    """
    
    def __init__(self):
        if not SAML_AVAILABLE:
            raise RuntimeError(
                "python3-saml library not installed. "
                "Install with: pip install python3-saml"
            )
        
        self.saml_settings = {
            "strict": True,
            "debug": False,
            "sp": {
                "entityId": settings.SAML_SP_ENTITY_ID,
                "assertionConsumerService": {
                    "url": settings.SAML_ACS_URL,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                },
                "x509cert": settings.SAML_SP_CERT,
                "privateKey": settings.SAML_SP_KEY,
            },
            "idp": {
                "entityId": settings.SAML_IDP_ENTITY_ID,
                "singleSignOnService": {
                    "url": settings.SAML_IDP_SSO_URL,
                    "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                },
                "x509cert": settings.SAML_IDP_CERT,
            },
            "security": {
                "authnRequestsSigned": True,
                "wantAssertionsSigned": True,
                "wantMessagesSigned": False,
                "wantAttributeStatement": True,
                "rejectUnsolicitedResponsesWithInResponseTo": True,
            },
        }
    
    def get_login_url(
        self,
        request_data: dict,
        relay_state: Optional[str] = None,
    ) -> ProviderAuthorization:
        """
        Generate SAML AuthnRequest redirect URL.
        
        Args:
            request_data: Dict with 'https', 'http_host', 'script_name', 'get_data'
            relay_state: Optional state to pass through the SAML flow
            
        Returns:
            URL to redirect user to for authentication
        """
        auth = self._init_saml_auth(request_data)
        url = auth.login(return_to=relay_state)
        return ProviderAuthorization(auth_url=url, request_id=auth.get_last_request_id())
    
    async def handle_callback(
        self,
        request_data: dict,
        post_data: dict,
        request_id: str,
    ) -> VerifiedExternalIdentity:
        """
        Process SAML Response and extract user attributes.
        
        Args:
            request_data: Dict with 'https', 'http_host', 'script_name', 'get_data'
            post_data: POST form data containing the SAML response
            
        Returns:
            SAMLUserInfo with extracted user attributes
            
        Raises:
            ValueError: If SAML validation fails or required attributes missing
        """
        request_data['post_data'] = post_data
        auth = self._init_saml_auth(request_data)
        auth.process_response(request_id=request_id)
        errors = auth.get_errors()
        
        if errors:
            raise ValueError("SAML response validation failed")
        
        if not auth.is_authenticated():
            raise ValueError("SAML authentication failed")
        
        # Extract SAML attributes (provided by UIBK IdP from their LDAP directory)
        attributes = auth.get_attributes()
        
        # Validate email is present and has valid format
        # Common SAML attribute names for email:
        # - 'mail' (friendly name)
        # - 'urn:oid:0.9.2342.19200300.100.1.3' (OID format)
        email = (
            attributes.get('mail', [None])[0] or 
            attributes.get('urn:oid:0.9.2342.19200300.100.1.3', [None])[0]
        )
        if not email:
            raise ValueError("SAML response missing required 'mail' attribute")
        
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            raise ValueError("SAML response contained an invalid email address")

        subject = auth.get_nameid()
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("SAML response missing a stable subject identifier")
        
        return VerifiedExternalIdentity(
            email=email.strip().lower(),
            name=attributes.get('displayName', [None])[0] or attributes.get('cn', [None])[0],
            picture_url=None,
            subject=subject.strip(),
        )

    @staticmethod
    def request_data(*, query: dict | None = None, post: dict | None = None) -> dict:
        """Build python3-saml request metadata from the configured, registered ACS."""
        acs = urlparse(settings.SAML_ACS_URL)
        return {
            "https": "on" if acs.scheme == "https" else "off",
            "http_host": acs.netloc,
            "script_name": acs.path,
            "get_data": query or {},
            "post_data": post or {},
        }
    
    def _init_saml_auth(self, request_data: dict) -> 'OneLogin_Saml2_Auth':
        """
        Initialize SAML auth object from request data.
        
        Args:
            request_data: Dict with request info (https, http_host, etc.)
            
        Returns:
            Initialized OneLogin_Saml2_Auth object
        """
        req = {
            'https': request_data.get('https', 'off'),
            'http_host': request_data.get('http_host', 'localhost'),
            'script_name': request_data.get('script_name', ''),
            'get_data': request_data.get('get_data', {}),
            'post_data': request_data.get('post_data', {}),
        }
        return OneLogin_Saml2_Auth(req, self.saml_settings)
    
    def get_metadata(self) -> str:
        """
        Generate SP metadata XML for ACOnet registration.
        
        Returns:
            XML string containing SP metadata
        """
        return OneLogin_Saml2_Utils.get_sp_metadata(self.saml_settings)


def is_saml_available() -> bool:
    """Check if SAML library is available."""
    return SAML_AVAILABLE
