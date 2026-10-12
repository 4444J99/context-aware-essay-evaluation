"""Durable opaque-login index; all token/state payloads live in the encrypted vault."""
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
import stat
import time
from uuid import uuid4

from .durable_vault import DurableVault


class SessionStore:
    def __init__(self, root: Path, vault: DurableVault, clock=time.time):
        if vault.domain != "session":
            raise ValueError("session_security_domain_required")
        root.mkdir(mode=0o700, exist_ok=True)
        info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("private_session_directory_required")
        self.path = root / "sessions.sqlite3"
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        info = os.fstat(fd)
        os.close(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError("private_session_index_required")
        self.vault = vault
        self.clock = clock
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), scope TEXT NOT NULL)")
            db.execute("INSERT OR IGNORE INTO metadata VALUES (1, ?)", (str(uuid4()),))
            self.scope = db.execute("SELECT scope FROM metadata WHERE id=1").fetchone()[0]
            db.execute("CREATE TABLE IF NOT EXISTS sessions (digest TEXT NOT NULL, kind TEXT NOT NULL, object_id TEXT NOT NULL, expires INTEGER NOT NULL, used INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(digest,kind))")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        try:
            conn.execute("PRAGMA synchronous=FULL")
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def digest(opaque: str):
        if not isinstance(opaque, str) or not 32 <= len(opaque) <= 256:
            raise ValueError("opaque_session_id_invalid")
        return sha256(opaque.encode()).hexdigest()

    def create(self, kind, opaque, payload, expires):
        if kind not in {"attempt", "browser"} or expires <= int(self.clock()):
            raise ValueError("session_kind_or_expiry_invalid")
        digest = self.digest(opaque)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM sessions WHERE used=0 AND expires>?", (int(self.clock()),)).fetchone()[0] >= 1000:
                raise ValueError("active_session_limit")
            object_id = self.vault.put(self.scope, {"kind": kind, "digest": digest, "expires": expires, "payload": payload})
            db.execute("INSERT INTO sessions (digest,kind,object_id,expires) VALUES (?,?,?,?)", (digest, kind, object_id, expires))

    def get(self, kind, opaque, consume=False):
        try:
            digest = self.digest(opaque)
        except ValueError:
            return None
        now = int(self.clock())
        with self.connect() as db:
            if consume:
                row = db.execute("UPDATE sessions SET used=1 WHERE digest=? AND kind=? AND used=0 AND expires>? RETURNING object_id", (digest, kind, now)).fetchone()
            else:
                row = db.execute("SELECT object_id FROM sessions WHERE digest=? AND kind=? AND used=0 AND expires>?", (digest, kind, now)).fetchone()
        if row is None:
            return None
        value = self.vault.get(self.scope, row[0])
        if value["digest"] != digest or value["kind"] != kind or value["expires"] <= now:
            return None
        return value["payload"]

    def revoke(self, kind, opaque):
        try:
            digest = self.digest(opaque)
        except ValueError:
            return
        with self.connect() as db:
            db.execute("UPDATE sessions SET used=1 WHERE digest=? AND kind=?", (digest, kind))
