import pytest
from src.utils.crypto import encrypt, decrypt, clear_key_cache

# Test user and twin IDs
TEST_USER = "user-123"
TEST_TWIN = "twin-456"

@pytest.fixture(autouse=True)
def reset_cache():
    """Clear key cache between tests."""
    clear_key_cache()

def test_encrypt_decrypt_roundtrip():
    """Encrypted value should decrypt back to original."""
    secret = "my-super-secret-password"
    encrypted = encrypt(secret, TEST_USER, TEST_TWIN)
    
    assert encrypted != secret  # Should be different
    assert encrypted.startswith("gAAAAA")  # Fernet prefix
    assert decrypt(encrypted, TEST_USER, TEST_TWIN) == secret  # Should roundtrip

def test_empty_string():
    """Empty strings should pass through unchanged."""
    assert encrypt("", TEST_USER, TEST_TWIN) == ""
    assert decrypt("", TEST_USER, TEST_TWIN) == ""

def test_unicode():
    """Unicode characters should work."""
    secret = "пароль-中文-🔐"
    encrypted = encrypt(secret, TEST_USER, TEST_TWIN)
    assert decrypt(encrypted, TEST_USER, TEST_TWIN) == secret

def test_different_users_different_keys():
    """Different users should produce different ciphertexts."""
    secret = "shared-secret"
    user1_encrypted = encrypt(secret, "user-1", TEST_TWIN)
    user2_encrypted = encrypt(secret, "user-2", TEST_TWIN)
    
    assert user1_encrypted != user2_encrypted  # Different keys
    
    # Each user can only decrypt their own
    assert decrypt(user1_encrypted, "user-1", TEST_TWIN) == secret
    assert decrypt(user2_encrypted, "user-2", TEST_TWIN) == secret
    
    # Cross-decryption should fail
    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt(user1_encrypted, "user-2", TEST_TWIN)

def test_different_twins_different_keys():
    """Different twins should produce different ciphertexts."""
    secret = "shared-secret"
    twin1_encrypted = encrypt(secret, TEST_USER, "twin-1")
    twin2_encrypted = encrypt(secret, TEST_USER, "twin-2")
    
    assert twin1_encrypted != twin2_encrypted  # Different keys
