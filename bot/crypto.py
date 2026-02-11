"""
Детерминированное шифрование для PII (email, телефон).
Один и тот же текст всегда даёт один и тот же зашифрованный результат.
Используется для хранения в БД и для согласованности с UTM-токенами.
"""
import base64
import secrets
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend


def _get_key(key_bytes: bytes) -> bytes:
    """Ensure key is 32 bytes for AES-256."""
    if len(key_bytes) >= 32:
        return key_bytes[:32]
    # Pad with zero or hash; for simplicity repeat and trim
    while len(key_bytes) < 32:
        key_bytes = key_bytes + key_bytes
    return key_bytes[:32]


def encrypt(plaintext: str, key: bytes) -> str:
    """
    Шифрует строку. Один и тот же plaintext + key → один и тот же результат.
    Возвращает base64url-строку (без +/-, подходит для URL).
    """
    if not plaintext:
        return ""
    key = _get_key(key)
    data = plaintext.encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    ct = encryptor.update(padded) + encryptor.finalize()
    return base64.urlsafe_b64encode(ct).decode("ascii").rstrip("=")


def decrypt(ciphertext: str, key: bytes) -> str:
    """Расшифровывает строку, зашифрованную encrypt()."""
    if not ciphertext:
        return ""
    key = _get_key(key)
    # Restore padding for base64
    pad = 4 - len(ciphertext) % 4
    if pad != 4:
        ciphertext += "=" * pad
    try:
        ct = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    except Exception:
        return ""
    cipher = Cipher(algorithms.AES(key), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    padded = decryptor.update(ct) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    data = unpadder.update(padded) + unpadder.finalize()
    return data.decode("utf-8")


def generate_token(length: int = 8) -> str:
    """Короткий уникальный токен для UTM (только буквы и цифры)."""
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    return "".join(secrets.choice(alphabet) for _ in range(length))
