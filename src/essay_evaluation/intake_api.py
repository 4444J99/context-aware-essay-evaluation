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


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section_id: UUID
    label: Literal["Fictional writing assignment"] = "Fictional writing assignment"


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_revision: UUID
    expected_generation: int = Field(ge=0, le=2_147_483_646)
    action: Literal["mapping", "exclude", "restore"]
    assignment_id: UUID | None = None
    enrollment_id: UUID | None = None
    reason: Literal["duplicate", "wrong_assignment", "withdrawn", "instructor_correction"] | None = None


class RosterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_generation: int = Field(ge=0, le=2_147_483_646)
    enrollment_ids: list[UUID] = Field(max_length=1000)


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

    @app.get("/v1/courses/{course_id}/intake-workspace")
    def workspace(course_id: UUID, scope=Depends(scoped, scope="function")):
        return run(scope, course_id, lambda repo: service.workspace(repo))

    @app.post("/v1/courses/{course_id}/assignments", status_code=201)
    def assignment(course_id: UUID, body: AssignmentCreate, scope=Depends(scoped, scope="function")):
        return run(scope, course_id, lambda repo: repo.create_assignment(body.section_id, body.label))

    @app.post("/v1/courses/{course_id}/intake/{submission_id}/resolution")
    def resolve(course_id: UUID, submission_id: UUID, body: Resolution, scope=Depends(scoped, scope="function")):
        return run(scope, course_id, lambda repo: service.resolve(repo, submission_id, body.source_revision, body.expected_generation, body.action, body.assignment_id, body.enrollment_id, body.reason))

    @app.post("/v1/courses/{course_id}/assignments/{assignment_id}/roster")
    def update_roster(course_id: UUID, assignment_id: UUID, body: RosterUpdate, scope=Depends(scoped, scope="function")):
        return run(scope, course_id, lambda repo: service.update_roster(repo, assignment_id, body.expected_generation, body.enrollment_ids))

    @app.get("/v1/courses/{course_id}/assignments/{assignment_id}/roster")
    def roster_history(course_id: UUID, assignment_id: UUID, scope=Depends(scoped, scope="function")):
        return run(scope, course_id, lambda repo: repo.roster_history(assignment_id))
