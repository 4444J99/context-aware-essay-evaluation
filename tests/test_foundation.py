from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import uuid

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient
import pytest

from essay_evaluation.api import create_app
from essay_evaluation.domain import (CacheMode, ContractError, Criterion, Evidence,
    ReleaseInputs, RetentionPolicy, Rubric, release_holds)
from essay_evaluation.privacy import scrub
from essay_evaluation.vault import EncryptedVault


def test_scrubs_direct_identifiers_and_preserves_literature():
    text = "Morgan Example morgan@example.invalid Student ID: TEST-1042\nShakespeare wrote Macbeth."
    result = scrub(text, ("Morgan Example",))
    assert "Morgan Example" not in result.text
    assert "morgan@example.invalid" not in result.text
    assert "TEST-1042" not in result.text
    assert "Shakespeare wrote Macbeth." in result.text
    assert result.contextual_review_required


def test_stable_placeholders_and_original_source_mapping():
    text = "Taylor Fiction argues clearly. Taylor Fiction supports the claim."
    result = scrub(text, ("Taylor Fiction",))
    assert result.text.count("[PERSON_1]") == 2
    quote = "supports the claim."
    start = result.text.index(quote)
    a, b = result.original_span(start, start+len(quote))
    assert text[a:b] == quote
    with pytest.raises(ValueError, match="redaction"):
        result.original_span(0, 10)


def test_identifier_case_and_overlap():
    result = scrub("Morgan Example, MORGAN EXAMPLE; Morgan.", ("Morgan", "Morgan Example"))
    assert result.text == "[PERSON_1], [PERSON_1]; [PERSON_2]."


def test_contextual_story_never_claims_anonymity():
    result = scrub("I was the only speaker at last Tuesday's neighborhood hearing.")
    assert result.contextual_review_required
    assert result.replacements == ()


def test_phone_and_email():
    result = scrub("Call (202) 555-0142 or +1 202-555-0143; x.y+z@example.invalid")
    assert "555" not in result.text
    assert "@example" not in result.text
    assert len(result.replacements) == 3


def test_input_limits():
    with pytest.raises(ValueError):
        scrub("a" * 100001)
    with pytest.raises(ValueError):
        scrub("text", ("x",))


def make_rubric():
    return Rubric("v1", (
        Criterion("argument", Decimal(4), Decimal(".75")),
        Criterion("evidence", Decimal(4), Decimal(".25")),
    ))


def test_exact_rubric_arithmetic():
    assert make_rubric().total({"argument": Decimal(3), "evidence": Decimal(4)}) == Decimal("81.25")


@pytest.mark.parametrize("scores", [
    {"argument": Decimal(3)}, {"argument": Decimal(5), "evidence": Decimal(4)},
    {"argument": Decimal("NaN"), "evidence": Decimal(4)},
    {"argument": Decimal(3), "evidence": Decimal(-1)},
])
def test_invalid_scores_fail_closed(scores):
    with pytest.raises(ContractError):
        make_rubric().total(scores)


def test_invalid_rubric():
    with pytest.raises(ContractError):
        Rubric("v1", (Criterion("a", Decimal(4), Decimal(".5")),))
    with pytest.raises(ContractError):
        Rubric("v1", (Criterion("a", Decimal(4), Decimal(".5")),
                      Criterion("a", Decimal(4), Decimal(".5"))))


def test_evidence_must_match_version_and_exact_quote():
    text = "An argument with evidence."
    assert Evidence("v1", 3, 11, "argument").validate(text, "v1")
    assert not Evidence("v1", 3, 11, "argument").validate(text, "v2")
    assert not Evidence("v1", 3, 11, "evidence").validate(text, "v1")
    assert not Evidence("v1", -1, 11, "argument").validate(text, "v1")


def test_release_requires_all_gates_and_never_releases_synthetic():
    assert len(release_holds(ReleaseInputs())) == 7
    passed = dict(extraction_ok=True, identity_resolved=True, privacy_reviewed=True,
                  evidence_valid=True, rubric_valid=True, route_qualified=True,
                  scope_authorized=True)
    assert release_holds(ReleaseInputs(**passed)) == ()
    assert release_holds(ReleaseInputs(**passed, synthetic=True)) == ("synthetic_demonstration_only",)


def test_vault_encryption_tamper_and_scope(tmp_path):
    keys = {d: AESGCM.generate_key(bit_length=256) for d in ("identity", "content")}
    vault = EncryptedVault(tmp_path, keys)
    scope = str(uuid.uuid4())
    ref = vault.put("content", scope, {"text": "synthetic confidential passage"})
    file = tmp_path/"content"/scope/f"{ref}.sealed"
    assert b"synthetic confidential passage" not in file.read_bytes()
    assert file.stat().st_mode & 0o777 == 0o600
    assert vault.get("content", scope, ref)["text"] == "synthetic confidential passage"
    other_scope = str(uuid.uuid4())
    other_dir = tmp_path/"content"/other_scope
    other_dir.mkdir()
    (other_dir/f"{ref}.sealed").write_bytes(file.read_bytes())
    with pytest.raises(InvalidTag):
        vault.get("content", other_scope, ref)
    data = bytearray(file.read_bytes())
    data[-1] ^= 1
    file.write_bytes(data)
    with pytest.raises(InvalidTag):
        vault.get("content", scope, ref)
    with pytest.raises(ValueError):
        vault.get("content", "../escape", ref)


def test_vault_requires_separate_keys(tmp_path):
    key = AESGCM.generate_key(bit_length=256)
    with pytest.raises(ValueError):
        EncryptedVault(tmp_path, {"identity": key, "content": key})


def test_vault_rejects_unknown_domain_before_filesystem_write(tmp_path):
    vault = EncryptedVault(tmp_path, {d: AESGCM.generate_key(bit_length=256)
                                    for d in ("identity", "content")})
    with pytest.raises(ValueError, match="unknown_security_domain"):
        vault.put("../escape", str(uuid.uuid4()), {"text": "synthetic"})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("mode,expected_day", [
    (CacheMode.AFTER_RUN, 12), (CacheMode.HOURS_24, 13),
    (CacheMode.DAYS_7, 19), (CacheMode.TERM, 22),
])
def test_retention_modes(mode, expected_day):
    now = datetime(2026, 10, 12, tzinfo=timezone.utc)
    end = datetime(2026, 10, 15, tzinfo=timezone.utc)
    assert RetentionPolicy(mode, end).cache_expires(now).day == expected_day


def test_interrupted_run_expires_within_24_hours():
    now = datetime(2026, 10, 12, tzinfo=timezone.utc)
    policy = RetentionPolicy(CacheMode.AFTER_RUN, datetime(2026, 12, 15, tzinfo=timezone.utc))
    assert (policy.cache_expires(now, completed=False)-now).total_seconds() == 86400


def test_demo_api_is_synthetic_idempotent_and_held():
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/health").json()["real_student_data_enabled"] is False
        assert "Synthetic demonstration" in client.get("/").text
        headers = {"Idempotency-Key": "example-0001", "X-Demo-Token": app.state.token}
        first = client.post("/v1/demo/intake", json={"fixture_id": "argument"}, headers=headers)
        assert first.status_code == 200
        result = first.json()
        assert result["status"] == "held" and result["grade"] is None
        assert "Morgan Example" not in json.dumps(result)
        assert "contextual_review_required" in json.dumps(result)
        assert client.post("/v1/demo/intake", json={"fixture_id": "argument"}, headers=headers).json() == result
        assert client.post("/v1/demo/intake", json={"fixture_id": "literary"}, headers=headers).status_code == 409
        second = client.post("/v1/demo/intake", json={"fixture_id": "argument"}, headers={**headers, "Idempotency-Key": "example-0002"}).json()
        assert second["student_id"] == result["student_id"]
        assert second["run_id"] != result["run_id"]
        assert client.post("/v1/demo/intake", json={"fixture_id": "argument", "essay": "real text"}, headers=headers).status_code == 422
        assert client.post("/v1/demo/intake", json={"fixture_id": "unknown"}, headers=headers).status_code == 422
        assert client.post("/v1/demo/intake", json={"fixture_id": "argument"}, headers={"Idempotency-Key":"example-0003"}).status_code == 403
        vault_root = app.state.vault.root
    assert not vault_root.exists()
