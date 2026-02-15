from __future__ import annotations

import base64
import hashlib
import struct
import xml.etree.ElementTree as ET

from Crypto.Cipher import AES


class WeComCryptoError(RuntimeError):
    pass


def _pkcs7_unpad(data: bytes, block_size: int = 32) -> bytes:
    if not data:
        raise WeComCryptoError("empty payload")
    pad = data[-1]
    if pad < 1 or pad > block_size:
        raise WeComCryptoError("invalid padding length")
    if data[-pad:] != bytes([pad]) * pad:
        raise WeComCryptoError("invalid padding bytes")
    return data[:-pad]


def _sha1_signature(token: str, timestamp: str, nonce: str, encrypted: str) -> str:
    parts = [token, timestamp, nonce, encrypted]
    parts.sort()
    raw = "".join(parts).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


class WeComCrypto:
    def __init__(self, token: str, encoding_aes_key: str, receive_id: str) -> None:
        self.token = token.strip()
        self.receive_id = receive_id.strip()
        try:
            self.aes_key = base64.b64decode(encoding_aes_key + "=")
        except Exception as exc:
            raise WeComCryptoError("invalid encoding aes key") from exc
        if len(self.aes_key) != 32:
            raise WeComCryptoError("invalid aes key length")

    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        signature = _sha1_signature(self.token, timestamp, nonce, echostr)
        if signature != msg_signature:
            raise WeComCryptoError("signature mismatch")
        plaintext, _ = self._decrypt(encrypted=echostr)
        return plaintext

    def decrypt_message(
        self,
        raw_xml: str,
        msg_signature: str,
        timestamp: str,
        nonce: str,
    ) -> str:
        encrypted = self._extract_encrypt(raw_xml)
        signature = _sha1_signature(self.token, timestamp, nonce, encrypted)
        if signature != msg_signature:
            raise WeComCryptoError("signature mismatch")
        plaintext, _ = self._decrypt(encrypted=encrypted)
        return plaintext

    def _extract_encrypt(self, raw_xml: str) -> str:
        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as exc:
            raise WeComCryptoError("invalid xml body") from exc
        encrypted = (root.findtext("Encrypt") or "").strip()
        if not encrypted:
            raise WeComCryptoError("missing Encrypt field")
        return encrypted

    def _decrypt(self, encrypted: str) -> tuple[str, str]:
        try:
            encrypted_bytes = base64.b64decode(encrypted)
        except Exception as exc:
            raise WeComCryptoError("invalid encrypted payload") from exc

        cipher = AES.new(self.aes_key, AES.MODE_CBC, self.aes_key[:16])
        plain_padded = cipher.decrypt(encrypted_bytes)
        plain = _pkcs7_unpad(plain_padded, block_size=32)

        if len(plain) < 20:
            raise WeComCryptoError("decrypted payload too short")

        msg_len = struct.unpack("!I", plain[16:20])[0]
        start = 20
        end = start + msg_len
        if end > len(plain):
            raise WeComCryptoError("invalid msg length")

        msg = plain[start:end]
        receive_id = plain[end:].decode("utf-8", errors="ignore")
        if self.receive_id and receive_id and receive_id != self.receive_id:
            raise WeComCryptoError("receive id mismatch")
        return msg.decode("utf-8", errors="ignore"), receive_id
