"""Synthetic-only intake API. No real upload, inference, or grade release is enabled."""
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import secrets
import tempfile
import uuid

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .domain import CacheMode, RetentionPolicy, ReleaseInputs, release_holds, Criterion, Rubric
from .fixtures import FIXTURES
from .privacy import scrub
from .vault import EncryptedVault


class IntakeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixture_id: str = Field(min_length=1, max_length=40)
    cache_mode: CacheMode = CacheMode.TERM


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        with tempfile.TemporaryDirectory(prefix="essay-synthetic-") as directory:
            app.state.vault = EncryptedVault(Path(directory), {
                "identity": AESGCM.generate_key(bit_length=256),
                "content": AESGCM.generate_key(bit_length=256),
            })
            app.state.scope = str(uuid.uuid4())
            app.state.token = secrets.token_urlsafe(32)  # allow-secret: generated per-process demo nonce, no credential literal
            app.state.cache = {}
            app.state.students = {}
            yield

    app = FastAPI(title="edu Essay Evaluation", version="0.1.0", lifespan=lifespan)
    app.state.storage_mode = "ephemeral_encrypted_synthetic"

    @app.get("/health")
    def health():
        return {
            "status": "ok", "product": "edu", "component": "essay-evaluation",
            "mode": "synthetic_only", "real_student_data_enabled": False,
            "inference_enabled": False, "automatic_grade_release_enabled": False,
        }

    @app.get("/v1/capabilities")
    def capabilities():
        return {
            "fixtures": list(FIXTURES), "cache_modes": [m.value for m in CacheMode],
            "implemented": ["direct_identifier_scrubbing", "encrypted_ephemeral_storage",
                            "rubric_contract", "source_span_mapping", "release_holds"],
            "pending": ["oidc", "kms_vault", "contextual_deidentification", "real_uploads",
                        "cloud_inference", "mac_companion", "semester_history", "nextjs_workspace"],
        }

    @app.get("/", response_class=HTMLResponse)
    def home():
        template = Path(__file__).with_name("demo.html").read_text()
        return HTMLResponse(template.replace("__TOKEN__", app.state.token),
                            headers={"Cache-Control": "no-store",
                                     "Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
                                     "X-Content-Type-Options": "nosniff"})

    @app.post("/v1/demo/intake")
    def intake(request: IntakeRequest,
               idempotency_key: str = Header(min_length=8, max_length=128),
               x_demo_token: str = Header(default="")):
        if not secrets.compare_digest(x_demo_token, app.state.token):
            raise HTTPException(403, "demo_session_required")
        if request.fixture_id not in FIXTURES:
            raise HTTPException(422, "unknown_synthetic_fixture")
        digest = hashlib.sha256(request.model_dump_json().encode()).hexdigest()
        if idempotency_key in app.state.cache:
            prior_digest, result = app.state.cache[idempotency_key]
            if prior_digest != digest:
                raise HTTPException(409, "idempotency_conflict")
            return result
        if len(app.state.cache) >= 100:
            raise HTTPException(429, "demo_run_limit")
        fixture = FIXTURES[request.fixture_id]
        if request.fixture_id not in app.state.students:
            student_id = str(uuid.uuid4())
            app.state.vault.put("identity", app.state.scope, {
                "student_id": student_id, "synthetic_name": fixture["name"],
            })
            app.state.students[request.fixture_id] = student_id
        student_id = app.state.students[request.fixture_id]
        clean = scrub(fixture["text"], (fixture["name"],))
        object_id = app.state.vault.put("content", app.state.scope, {
            "student_id": student_id, "original": fixture["text"], "scrubbed": clean.text,
            "spans": [asdict(r) for r in clean.replacements],
        })
        rubric = Rubric("synthetic-rubric-v1", (
            Criterion("argument", Decimal("4"), Decimal("0.5")),
            Criterion("evidence", Decimal("4"), Decimal("0.5")),
        ))
        now = datetime.now(timezone.utc)
        policy = RetentionPolicy(request.cache_mode,
                                 datetime(now.year, 12, 15, tzinfo=timezone.utc))
        holds = release_holds(ReleaseInputs(
            extraction_ok=True, identity_resolved=True, rubric_valid=True,
            scope_authorized=True, synthetic=True,
        ))
        result = {
            "run_id": str(uuid.uuid4()), "student_id": student_id,
            "submission_ref": object_id, "mode": "synthetic_only",
            "status": "held", "holds": holds, "scrubbed_text": clean.text,
            "redaction_counts": {category: sum(r.category == category for r in clean.replacements)
                                 for category in sorted({r.category for r in clean.replacements})},
            "rubric_version": rubric.version, "grade": None,
            "privacy": {"direct_identifiers_scrubbed": True,
                        "contextual_review_required": True, "anonymous": False},
            "storage": {"adapter": app.state.storage_mode, "identity_key_separate": True,
                        "destroyed_on_shutdown": True},
            "retention_preview": {"cache_mode": policy.mode.value,
                                  "cache_expires_at": policy.cache_expires(now).isoformat(),
                                  "applied": False, "vault_deletion_scheduled": False},
        }
        app.state.cache[idempotency_key] = (digest, result)
        return result

    return app
