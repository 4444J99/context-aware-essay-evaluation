"""Authenticated fixture-only intake routes; no arbitrary student upload capability."""
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .intake import IntakeConflict, IntakeStorageError, SqlIntakeRepository


class FixtureIntake(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    fixture_id: Literal["argument", "literary", "contextual", "docx-argument", "pdf-held"]


class PrivacyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_revision: UUID
    expected_generation: int = Field(ge=0, le=2_147_483_646)
    decisions: dict[int, Literal["retain", "redact", "hold"]] = Field(max_length=2000)


def install_intake_routes(app, scoped, service):
    @app.exception_handler(IntakeStorageError)
    async def storage_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": "intake_storage_unavailable"})

    def run(scope, course, action):
        if service is None:
            raise HTTPException(503, "protected_intake_unconfigured")
        repo = SqlIntakeRepository(scope[0], scope[1], course)
        try:
            return action(repo)
        except IntakeConflict as error:
            raise HTTPException(409, str(error)) from None
        except LookupError:
            raise HTTPException(404, "record_not_found") from None
        except ValueError:
            raise HTTPException(422, "intake_or_review_invalid") from None

    @app.post("/v1/courses/{course_id}/intake", status_code=201)
    def intake(course_id: UUID, body: FixtureIntake, scope=Depends(scoped, scope="function")):
        return run(scope, course_id, lambda repo: service.ingest(repo, body.request_id, body.fixture_id))

    @app.get("/v1/courses/{course_id}/intake/{submission_id}/review")
    def review(course_id: UUID, submission_id: UUID, scope=Depends(scoped, scope="function")):
        return run(scope, course_id, lambda repo: service.review_view(repo, submission_id))

    @app.post("/v1/courses/{course_id}/intake/{submission_id}/review")
    def decide(course_id: UUID, submission_id: UUID, body: PrivacyDecision, scope=Depends(scoped, scope="function")):
        return run(scope, course_id, lambda repo: service.decide(repo, submission_id, body.source_revision, body.expected_generation, body.decisions))
