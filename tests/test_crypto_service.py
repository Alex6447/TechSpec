import base64
import secrets

import pytest

from app.services.crypto_service import decrypt, encrypt


def make_master_key() -> str:
    """Generate a valid base64-encoded 32-byte master key."""
    return base64.b64encode(secrets.token_bytes(32)).decode()


class TestEncryptDecrypt:
    def test_round_trip(self):
        key = make_master_key()
        plaintext = "hello, world!"
        assert decrypt(encrypt(plaintext, key), key) == plaintext

    def test_round_trip_empty_string(self):
        key = make_master_key()
        assert decrypt(encrypt("", key), key) == ""

    def test_round_trip_unicode(self):
        key = make_master_key()
        plaintext = "секретный токен 🔑"
        assert decrypt(encrypt(plaintext, key), key) == plaintext

    def test_round_trip_long_string(self):
        key = make_master_key()
        plaintext = "x" * 10_000
        assert decrypt(encrypt(plaintext, key), key) == plaintext

    def test_encrypt_produces_different_ciphertexts(self):
        """Each encrypt call uses a random nonce — same plaintext yields different output."""
        key = make_master_key()
        plaintext = "same text"
        ct1 = encrypt(plaintext, key)
        ct2 = encrypt(plaintext, key)
        assert ct1 != ct2

    def test_encrypt_returns_str(self):
        key = make_master_key()
        result = encrypt("data", key)
        assert isinstance(result, str)

    def test_decrypt_returns_str(self):
        key = make_master_key()
        ct = encrypt("data", key)
        assert isinstance(decrypt(ct, key), str)

    def test_wrong_key_raises(self):
        key1 = make_master_key()
        key2 = make_master_key()
        ct = encrypt("secret", key1)
        with pytest.raises(Exception):
            decrypt(ct, key2)

    def test_tampered_ciphertext_raises(self):
        key = make_master_key()
        ct_bytes = base64.b64decode(encrypt("secret", key))
        # Flip a byte in the encrypted payload
        tampered = ct_bytes[:12] + bytes([ct_bytes[12] ^ 0xFF]) + ct_bytes[13:]
        with pytest.raises(Exception):
            decrypt(base64.b64encode(tampered).decode(), key)

    def test_invalid_key_length_raises(self):
        """Keys that are not 16/24/32 bytes must be rejected by AESGCM."""
        bad_key = base64.b64encode(b"short").decode()
        with pytest.raises(Exception):
            encrypt("data", bad_key)
