"""Authenticated encrypted local adapter for synthetic development.

Production KMS/object storage and separate identity-service credentials are later tranches.
No plaintext key or payload is written by this adapter.
"""
import json
import os
from pathlib import Path
import uuid
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class EncryptedVault:
    def __init__(self, root: Path, keys: dict[str, bytes]):
        if set(keys) != {"identity", "content"}:
            raise ValueError("separate_domain_keys_required")
        if keys["identity"] == keys["content"]:
            raise ValueError("domain_keys_must_differ")
        self.root = root
        self._ciphers = {domain: AESGCM(key) for domain, key in keys.items()}
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)

    @staticmethod
    def _validate(scope: str, object_id: str):
        # Opaque UUIDs only: no user-controlled filesystem paths.
        uuid.UUID(scope)
        uuid.UUID(object_id)

    def put(self, domain: str, scope: str, payload: dict) -> str:
        object_id = str(uuid.uuid4())
        if domain not in self._ciphers:
            raise ValueError("unknown_security_domain")
        self._validate(scope, object_id)
        directory = self.root / domain / scope
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        aad = f"v1:{domain}:{scope}:{object_id}".encode()
        nonce = os.urandom(12)
        sealed = nonce + self._ciphers[domain].encrypt(
            nonce, json.dumps(payload, ensure_ascii=False).encode(), aad
        )
        path = directory / f"{object_id}.sealed"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(sealed)
        return object_id

    def get(self, domain: str, scope: str, object_id: str) -> dict:
        if domain not in self._ciphers:
            raise ValueError("unknown_security_domain")
        self._validate(scope, object_id)
        data = (self.root/domain/scope/f"{object_id}.sealed").read_bytes()
        aad = f"v1:{domain}:{scope}:{object_id}".encode()
        plain = self._ciphers[domain].decrypt(data[:12], data[12:], aad)
        return json.loads(plain)
