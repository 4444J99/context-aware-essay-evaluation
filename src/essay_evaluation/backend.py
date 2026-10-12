"""Protected edu metadata API, kept separate from the unauthenticated synthetic demo."""
from contextlib import asynccontextmanager
from datetime import date
import os
from typing import Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator
import psycopg

from .auth import AuthenticationError, TokenVerifier
from .database import Database


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TermInput(Input):
    label: str = Field(min_length=1, max_length=160)
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def date_order(self):
        if self.ends_on < self.starts_on:
            raise ValueError("term_date_order")
        return self


class CourseInput(Input):
    term_id: UUID
    title: str = Field(min_length=1, max_length=160)


class SectionInput(Input):
    label: str = Field(min_length=1, max_length=160)


class ReferenceInput(Input):
    source: Literal["teacher_dashboard", "aetheria", "edu"]
    kind: Literal["course", "section", "enrollment"]
    external_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    target_id: UUID


def create_backend(database: Database, verifier: TokenVerifier) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        database.verify()
        yield

    app = FastAPI(title="edu Protected Backend", version="0.2.0", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    def scoped(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials is None:
            raise HTTPException(401, "authentication_required", headers={"WWW-Authenticate": "Bearer"})
        try:
            identity = verifier.verify(credentials.credentials)
        except AuthenticationError:
            raise HTTPException(401, "invalid_identity_or_mfa", headers={"WWW-Authenticate": "Bearer"}) from None
        try:
            with database.scoped(identity.issuer, identity.subject) as scope:
                yield scope
        except PermissionError:
            raise HTTPException(403, "instructor_not_provisioned") from None

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        # Never reflect supplied values, names or tokens in validation responses.
        return JSONResponse(status_code=422, content={"detail": "invalid_request", "fields": [
            {"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()
        ]})

    @app.exception_handler(psycopg.Error)
    async def database_error(request, exc):
        if isinstance(exc, psycopg.IntegrityError):
            return JSONResponse(status_code=409, content={"detail": "scope_or_record_conflict"})
        return JSONResponse(status_code=503, content={"detail": "storage_unavailable"})

    def require(conn, table, key, owner, course=None):
        # table is selected only from literal server call sites.
        sql = psycopg.sql.SQL("SELECT id FROM {} WHERE id=%s AND instructor_id=%s").format(psycopg.sql.Identifier(table))
        params = [key, owner]
        if course is not None:
            sql += psycopg.sql.SQL(" AND course_id=%s")
            params.append(course)
        if conn.execute(sql, params).fetchone() is None:
            raise HTTPException(404, "record_not_found")

    def page(rows):
        return {"items": rows[:100], "next_cursor": str(rows[99]["id"]) if len(rows) > 100 else None}

    @app.get("/health")
    def health():
        return {"product": "edu", "component": "essay-evaluation", "mode": "protected_metadata",
                "real_student_data_enabled": False, "inference_enabled": False}

    @app.get("/v1/session")
    def session(scope=Depends(scoped, scope="function")):
        return {"instructor_id": scope[1], "product": "edu", "mfa_verified": True}

    @app.post("/v1/terms", status_code=201)
    def create_term(body: TermInput, scope=Depends(scoped, scope="function")):
        conn, owner = scope
        return conn.execute("INSERT INTO terms VALUES (%s,%s,%s,%s,%s) RETURNING id,label,starts_on,ends_on",
                            (uuid4(), owner, body.label, body.starts_on, body.ends_on)).fetchone()

    @app.get("/v1/terms")
    def terms(after: UUID | None = Query(default=None), scope=Depends(scoped, scope="function")):
        conn, owner = scope
        return page(conn.execute("SELECT id,label,starts_on,ends_on FROM terms WHERE instructor_id=%s AND (%s::uuid IS NULL OR id>%s) ORDER BY id LIMIT 101", (owner, after, after)).fetchall())

    @app.post("/v1/courses", status_code=201)
    def create_course(body: CourseInput, scope=Depends(scoped, scope="function")):
        conn, owner = scope
        require(conn, "terms", body.term_id, owner)
        return conn.execute("INSERT INTO courses VALUES (%s,%s,%s,%s) RETURNING id,term_id,title",
                            (uuid4(), owner, body.term_id, body.title)).fetchone()

    @app.get("/v1/courses")
    def courses(after: UUID | None = Query(default=None), scope=Depends(scoped, scope="function")):
        conn, owner = scope
        return page(conn.execute("SELECT id,term_id,title FROM courses WHERE instructor_id=%s AND (%s::uuid IS NULL OR id>%s) ORDER BY id LIMIT 101", (owner, after, after)).fetchall())

    @app.get("/v1/courses/{course_id}")
    def course(course_id: UUID, scope=Depends(scoped, scope="function")):
        conn, owner = scope
        require(conn, "courses", course_id, owner)
        return conn.execute("SELECT id,term_id,title FROM courses WHERE id=%s AND instructor_id=%s", (course_id, owner)).fetchone()

    @app.post("/v1/courses/{course_id}/sections", status_code=201)
    def create_section(course_id: UUID, body: SectionInput, scope=Depends(scoped, scope="function")):
        conn, owner = scope
        require(conn, "courses", course_id, owner)
        return conn.execute("INSERT INTO sections VALUES (%s,%s,%s,%s) RETURNING id,course_id,label", (uuid4(), owner, course_id, body.label)).fetchone()

    @app.get("/v1/courses/{course_id}/sections")
    def sections(course_id: UUID, after: UUID | None = Query(default=None), scope=Depends(scoped, scope="function")):
        conn, owner = scope
        require(conn, "courses", course_id, owner)
        return page(conn.execute("SELECT id,course_id,label FROM sections WHERE instructor_id=%s AND course_id=%s AND (%s::uuid IS NULL OR id>%s) ORDER BY id LIMIT 101", (owner, course_id, after, after)).fetchall())

    @app.post("/v1/courses/{course_id}/sections/{section_id}/enrollments", status_code=201)
    def enroll(course_id: UUID, section_id: UUID, body: Input | None = None, scope=Depends(scoped, scope="function")):
        conn, owner = scope
        require(conn, "sections", section_id, owner, course_id)
        return conn.execute("INSERT INTO enrollments VALUES (%s,%s,%s,%s,%s) RETURNING id,course_id,section_id,student_ref", (uuid4(), owner, course_id, section_id, uuid4())).fetchone()

    @app.get("/v1/courses/{course_id}/sections/{section_id}/enrollments")
    def enrollments(course_id: UUID, section_id: UUID, after: UUID | None = Query(default=None), scope=Depends(scoped, scope="function")):
        conn, owner = scope
        require(conn, "sections", section_id, owner, course_id)
        return page(conn.execute("SELECT id,course_id,section_id,student_ref FROM enrollments WHERE instructor_id=%s AND course_id=%s AND section_id=%s AND (%s::uuid IS NULL OR id>%s) ORDER BY id LIMIT 101", (owner, course_id, section_id, after, after)).fetchall())

    @app.post("/v1/courses/{course_id}/references", status_code=201)
    def reference(course_id: UUID, body: ReferenceInput, scope=Depends(scoped, scope="function")):
        conn, owner = scope
        require(conn, "courses", course_id, owner)
        if body.kind == "course":
            if body.target_id != course_id:
                raise HTTPException(404, "record_not_found")
        else:
            require(conn, {"section": "sections", "enrollment": "enrollments"}[body.kind], body.target_id, owner, course_id)
        return conn.execute("INSERT INTO external_references VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id,course_id,source,kind,external_id,target_id",
                            (uuid4(), owner, course_id, body.source, body.kind, body.external_id, body.target_id)).fetchone()

    @app.get("/v1/courses/{course_id}/references")
    def references(course_id: UUID, after: UUID | None = Query(default=None), scope=Depends(scoped, scope="function")):
        conn, owner = scope
        require(conn, "courses", course_id, owner)
        return page(conn.execute("SELECT id,course_id,source,kind,external_id,target_id FROM external_references WHERE instructor_id=%s AND course_id=%s AND (%s::uuid IS NULL OR id>%s) ORDER BY id LIMIT 101", (owner, course_id, after, after)).fetchall())

    return app


def configured_backend() -> FastAPI:
    # Required operator-owned values: there is no anonymous or demo fallback.
    return create_backend(Database(os.environ["EDU_DATABASE_URL"]), TokenVerifier(
        os.environ["EDU_OIDC_ISSUER"], os.environ["EDU_OIDC_AUDIENCE"], os.environ["EDU_OIDC_JWKS_URL"],
    ))
