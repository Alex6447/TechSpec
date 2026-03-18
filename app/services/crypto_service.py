import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt(plaintext: str, master_key: str) -> str:
    """Encrypt plaintext string using AES-256-GCM.

    master_key — base64-encoded 32-byte key (from settings.master_key).
    Returns base64-encoded string: nonce (12 bytes) || ciphertext+tag.
    """
    key = base64.b64decode(master_key)
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    encrypted = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + encrypted).decode()


def decrypt(ciphertext: str, master_key: str) -> str:
    """Decrypt AES-256-GCM ciphertext produced by encrypt().

    master_key — base64-encoded 32-byte key (from settings.master_key).
    Returns original plaintext string.
    """
    key = base64.b64decode(master_key)
    data = base64.b64decode(ciphertext)
    nonce = data[:12]
    encrypted = data[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, encrypted, None).decode()
