"""Durable envelope-encrypted filesystem vault with one security domain per worker."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import fcntl
import json
import os
from pathlib import Path
import re
import stat
from typing import Protocol
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_PAYLOAD = 4 * 1024 * 1024
MAX_SEALED = 9 * 1024 * 1024


class KeyProvider(Protocol):
    """Deployments may supply a remote KMS without exposing its wrapping keys."""
    domain: str
    current: str

    def wrap(self, key: bytes, context: bytes) -> tuple[str, bytes]: ...
    def unwrap(self, version: str, sealed: bytes, context: bytes) -> bytes: ...


@dataclass(frozen=True)
class DomainKeyRing:
    """Externally supplied development keys. Never generated or saved by the vault."""
    domain: str
    current: str
    keys: dict[str, bytes] = field(repr=False)

    def __post_init__(self):
        if self.domain not in {"identity", "content", "session"} or self.current not in self.keys:
            raise ValueError("key_domain_or_version_invalid")
        for version, key in self.keys.items():
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", version) or len(key) != 32:
                raise ValueError("wrapping_key_invalid")

    def wrap(self, key: bytes, context: bytes) -> tuple[str, bytes]:
        nonce = os.urandom(12)
        return self.current, nonce + AESGCM(self.keys[self.current]).encrypt(
            nonce, key, context + b":" + self.current.encode(),
        )

    def unwrap(self, version: str, sealed: bytes, context: bytes) -> bytes:
        if version not in self.keys:
            raise ValueError("wrapping_key_version_unavailable")
        return AESGCM(self.keys[version]).decrypt(sealed[:12], sealed[12:], context + b":" + version.encode())


class DurableVault:
    def __init__(self, root: Path, provider: KeyProvider):
        if provider.domain not in {"identity", "content", "session"}:
            raise ValueError("key_domain_invalid")
        self.root = root
        self.provider = provider
        self.domain = provider.domain
        root.mkdir(mode=0o700, exist_ok=True)
        with self._directory() as fd:
            self._private_directory(fd)

    @staticmethod
    def _private_directory(fd):
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("private_owned_directory_required")

    @staticmethod
    def _uuid(value: str) -> str:
        if str(UUID(value)) != value:
            raise ValueError("canonical_uuid_required")
        return value

    @contextmanager
    def _directory(self, scope: str | None = None):
        descriptors = []
        try:
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.append(fd)
            self._private_directory(fd)
            for part in ([self.domain, self._uuid(scope)] if scope else []):
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
                fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                descriptors.append(fd)
                self._private_directory(fd)
            yield fd
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    def _context(self, scope, object_id):
        return f"edu-vault-v1:{self.domain}:{self._uuid(scope)}:{self._uuid(object_id)}".encode()

    @staticmethod
    def _read(fd, name):
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
                raise ValueError("private_owned_record_required")
            sealed = stream.read(MAX_SEALED + 1)
        if len(sealed) > MAX_SEALED:
            raise ValueError("sealed_record_too_large")
        return json.loads(sealed)

    @staticmethod
    def _write(fd, name, record, replace=False):
        data = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
        if len(data) > MAX_SEALED:
            raise ValueError("sealed_record_too_large")
        temporary = ".tmp-" + str(uuid4())
        file_fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        try:
            with os.fdopen(file_fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if replace:
                os.replace(temporary, name, src_dir_fd=fd, dst_dir_fd=fd)
            else:
                os.link(temporary, name, src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)
            os.fsync(fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=fd)
                os.fsync(fd)
            except FileNotFoundError:
                pass

    def put(self, scope: str, payload: dict) -> str:
        if not isinstance(payload, dict):
            raise ValueError("object_payload_required")
        plain = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        if len(plain) > MAX_PAYLOAD:
            raise ValueError("payload_too_large")
        object_id = str(uuid4())
        context = self._context(scope, object_id)
        data_key = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(12)
        version, wrapped = self.provider.wrap(data_key, context + b":wrap")
        record = {"format": 1, "key_version": version, "wrapped_key": wrapped.hex(),
                  "nonce": nonce.hex(), "ciphertext": AESGCM(data_key).encrypt(nonce, plain, context).hex()}
        with self._directory(scope) as fd:
            self._write(fd, object_id + ".sealed", record)
        return object_id

    def _open(self, record, context):
        if set(record) != {"format", "key_version", "wrapped_key", "nonce", "ciphertext"} or record["format"] != 1:
            raise ValueError("vault_format_invalid")
        data_key = self.provider.unwrap(record["key_version"], bytes.fromhex(record["wrapped_key"]), context + b":wrap")
        plain = AESGCM(data_key).decrypt(bytes.fromhex(record["nonce"]), bytes.fromhex(record["ciphertext"]), context)
        if len(plain) > MAX_PAYLOAD:
            raise ValueError("payload_too_large")
        return data_key, plain

    def get(self, scope: str, object_id: str) -> dict:
        context = self._context(scope, object_id)
        with self._directory(scope) as fd:
            record = self._read(fd, object_id + ".sealed")
        _, plain = self._open(record, context)
        payload = json.loads(plain)
        if not isinstance(payload, dict):
            raise ValueError("object_payload_required")
        return payload

    def rewrap(self, scope: str, object_id: str) -> None:
        """Atomically change wrapping key; preserve object ID and payload ciphertext."""
        context = self._context(scope, object_id)
        with self._directory(scope) as fd:
            fcntl.flock(fd, fcntl.LOCK_EX)
            record = self._read(fd, object_id + ".sealed")
            data_key, _ = self._open(record, context)
            version, wrapped = self.provider.wrap(data_key, context + b":wrap")
            record.update(key_version=version, wrapped_key=wrapped.hex())
            self._write(fd, object_id + ".sealed", record, replace=True)
