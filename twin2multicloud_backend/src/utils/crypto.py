"""
Per-User-Per-Twin Fernet Encryption for credentials at rest.

Each user+twin combination gets a unique encryption key derived from:
- Master key (ENCRYPTION_KEY in .env)
- User ID + Twin ID (used as salt)

This provides double isolation:
- Compromising one user's data doesn't expose other users
- Compromising one twin's data doesn't expose sibling twins

Uses PBKDF2 for key derivation + Fernet (AES-128-CBC) for encryption.
"""
import base64
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from src.config import settings

# Cache derived keys to avoid repeated derivation (key = "user_id:twin_id")
_key_cache: dict[str, Fernet] = {}


def _derive_key(user_id: str, twin_id: str) -> bytes:
    """
    Derive a unique Fernet key for a specific user+twin combination.
    
    Uses PBKDF2 with:
    - Master key as input
    - User ID + Twin ID as salt (ensures unique key per user per twin)
    - 100,000 iterations (OWASP recommendation)
    """
    salt = f"{user_id}:{twin_id}".encode()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    derived = kdf.derive(settings.ENCRYPTION_KEY.encode())
    return base64.urlsafe_b64encode(derived)


def _get_fernet(user_id: str, twin_id: str) -> Fernet:
    """Get or create Fernet instance for a user+twin combination."""
    cache_key = f"{user_id}:{twin_id}"
    if cache_key not in _key_cache:
        try:
            key = _derive_key(user_id, twin_id)
            _key_cache[cache_key] = Fernet(key)
        except Exception as e:
            raise ValueError(
                f"Invalid ENCRYPTION_KEY. Generate with: "
                f"python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            ) from e
    return _key_cache[cache_key]


def encrypt(plaintext: str, user_id: str, twin_id: str) -> str:
    """
    Encrypt a plaintext string using user+twin-specific key.
    
    Args:
        plaintext: The secret to encrypt
        user_id: The user ID (from current_user.id)
        twin_id: The twin ID
        
    Returns:
        Base64-encoded ciphertext (safe for DB storage)
    """
    if not plaintext:
        return ""
    if not user_id or not twin_id:
        raise ValueError("user_id and twin_id required for encryption")
    return _get_fernet(user_id, twin_id).encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str, user_id: str, twin_id: str) -> str:
    """
    Decrypt a ciphertext string using user+twin-specific key.
    
    Args:
        ciphertext: The encrypted value from DB
        user_id: The user ID (from current_user.id)
        twin_id: The twin ID
        
    Returns:
        Original plaintext secret
        
    Raises:
        ValueError: If decryption fails (wrong key or corrupted data)
    """
    if not ciphertext:
        return ""
    if not user_id or not twin_id:
        raise ValueError("user_id and twin_id required for decryption")
    try:
        return _get_fernet(user_id, twin_id).decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("Decryption failed - invalid key or corrupted data")


def clear_key_cache():
    """Clear cached keys (useful for testing or key rotation)."""
    _key_cache.clear()
