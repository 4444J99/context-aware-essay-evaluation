import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import pytest

from essay_evaluation.durable_vault import DomainKeyRing, DurableVault, MAX_PAYLOAD
from essay_evaluation.sessions import SessionStore


def keyring(domain="content", version="v1", keys=None):
    return DomainKeyRing(domain, version, keys or {version: AESGCM.generate_key(bit_length=256)})


def test_restart_and_ciphertext_restore(tmp_path):
    keys = keyring()
    root = tmp_path / "vault"
    scope = str(uuid4())
    object_id = DurableVault(root, keys).put(scope, {"text": "Invented classroom example"})
    assert DurableVault(root, keys).get(scope, object_id)["text"] == "Invented classroom example"
    archive = tmp_path / "restored"
    shutil.copytree(root, archive)
    assert DurableVault(archive, keys).get(scope, object_id)["text"] == "Invented classroom example"
    for file in root.rglob("*"):
        if file.is_file():
            assert b"Invented classroom example" not in file.read_bytes()
            assert file.stat().st_mode & 0o077 == 0
    assert not any(file.name.endswith("key") for file in root.rglob("*"))


def test_rotation_preserves_ciphertext_and_old_backup_requires_old_key(tmp_path):
    old = keyring()
    root, scope = tmp_path / "vault", str(uuid4())
    object_id = DurableVault(root, old).put(scope, {"synthetic": True})
    path = root / "content" / scope / (object_id + ".sealed")
    before = json.loads(path.read_text())
    new_key = AESGCM.generate_key(bit_length=256)
    rotating = keyring(version="v2", keys={**old.keys, "v2": new_key})
    DurableVault(root, rotating).rewrap(scope, object_id)
    after = json.loads(path.read_text())
    assert before["ciphertext"] == after["ciphertext"] and before["nonce"] == after["nonce"]
    assert after["key_version"] == "v2"
    assert DurableVault(root, keyring(version="v2", keys={"v2": new_key})).get(scope, object_id) == {"synthetic": True}
    path.write_text(json.dumps(before))
    with pytest.raises(ValueError, match="version_unavailable"):
        DurableVault(root, keyring(version="v2", keys={"v2": new_key})).get(scope, object_id)


def test_domain_scope_object_binding_and_tamper(tmp_path):
    root, scope = tmp_path / "vault", str(uuid4())
    identity = DurableVault(root, keyring("identity"))
    content = DurableVault(root, keyring("content"))
    object_id = identity.put(scope, {"invented_name": "Fictional Learner"})
    with pytest.raises(FileNotFoundError):
        content.get(scope, object_id)
    other_scope = str(uuid4())
    original = root / "identity" / scope / (object_id + ".sealed")
    destination = root / "identity" / other_scope
    destination.mkdir(mode=0o700)
    shutil.copy2(original, destination / original.name)
    with pytest.raises(InvalidTag):
        identity.get(other_scope, object_id)
    modified = json.loads(original.read_text())
    modified["ciphertext"] = f"{int(modified["ciphertext"][:2], 16) ^ 1:02x}" + modified["ciphertext"][2:]
    original.write_text(json.dumps(modified))
    with pytest.raises(InvalidTag):
        identity.get(scope, object_id)


def test_no_symlink_or_permissive_record_access(tmp_path):
    root, scope = tmp_path / "vault", str(uuid4())
    vault = DurableVault(root, keyring())
    object_id = vault.put(scope, {"test": True})
    record = root / "content" / scope / (object_id + ".sealed")
    record.chmod(0o644)
    with pytest.raises(ValueError, match="private_owned_record"):
        vault.get(scope, object_id)
    record.unlink()
    target = tmp_path / "outside"
    target.write_text("{}")
    record.symlink_to(target)
    with pytest.raises(OSError):
        vault.get(scope, object_id)
    with pytest.raises(ValueError):
        vault.put("../../outside", {})
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(OSError):
        DurableVault(alias, keyring())


def test_payload_bound_and_no_overwrite_on_failed_publish(tmp_path, monkeypatch):
    root, scope = tmp_path / "vault", str(uuid4())
    vault = DurableVault(root, keyring())
    with pytest.raises(ValueError, match="payload_too_large"):
        vault.put(scope, {"text": "x" * MAX_PAYLOAD})
    object_id = vault.put(scope, {"revision": 1})
    import essay_evaluation.durable_vault as module
    monkeypatch.setattr(module, "uuid4", lambda: object_id)
    with pytest.raises(FileExistsError):
        vault.put(scope, {"revision": 2})
    assert vault.get(scope, object_id) == {"revision": 1}
    assert not list(root.rglob(".tmp-*"))


def test_session_replay_expiry_revocation_and_restart(tmp_path):
    keys = keyring("session")
    vault = DurableVault(tmp_path / "vault", keys)
    now = [100]
    store = SessionStore(tmp_path / "index", vault, clock=lambda: now[0])
    opaque = "synthetic_session_identifier_00001"
    store.create("attempt", opaque, {"verifier": "synthetic-pkce-value"}, 200)
    assert store.get("attempt", opaque, consume=True)["verifier"] == "synthetic-pkce-value"
    assert store.get("attempt", opaque, consume=True) is None
    store.create("browser", opaque, {"access_token": "synthetic-not-a-real-token"}, 200)
    restarted = SessionStore(tmp_path / "index", DurableVault(tmp_path / "vault", keys), clock=lambda: now[0])
    assert restarted.get("browser", opaque)["access_token"] == "synthetic-not-a-real-token"
    assert b"synthetic-not-a-real-token" not in (tmp_path/"index"/"sessions.sqlite3").read_bytes()
    now[0] = 201
    assert restarted.get("browser", opaque) is None
    now[0] = 101
    restarted.revoke("browser", opaque)
    assert restarted.get("browser", opaque) is None
    assert keys.keys["v1"].hex() not in repr(keys)
