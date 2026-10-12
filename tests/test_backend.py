"""Real PostgreSQL acceptance; never substitute SQLite for row-security evidence."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
import jwt
import psycopg
from psycopg import sql
import pytest

from essay_evaluation.auth import AuthenticationError, TokenVerifier
from essay_evaluation.backend import create_backend
from essay_evaluation.database import Database, migrate, rollback_empty

ISSUER = "https://identity.example.test"
AUDIENCE = "edu-test-api"


@pytest.fixture(scope="module")
def signing():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = TokenVerifier(ISSUER, AUDIENCE, ISSUER + "/jwks")
    verifier.jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=key.public_key()))

    def token(subject="teacher-a", **changes):
        now = datetime.now(timezone.utc)
        claims = {"iss": ISSUER, "aud": AUDIENCE, "sub": subject, "iat": now,
                  "exp": now + timedelta(minutes=5), "amr": ["pwd", "otp"]}
        claims.update(changes)
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-generated"})
    return verifier, token


@pytest.mark.parametrize("changes", [
    {"iss": "https://wrong.example.test"}, {"aud": "wrong"},
    {"exp": 1}, {"iat": 4102444800}, {"sub": ""},
    {"amr": ["pwd"]}, {"amr": "mfa"}, {"amr": None}, {"exp": None},
])
def test_identity_rejections(signing, changes):
    verifier, token = signing  # allow-secret: public-key client or generated synthetic test-token helper; no credential literal
    with pytest.raises(AuthenticationError):
        verifier.verify(token(**changes))


def test_signature_algorithm_and_missing_claims(signing):
    verifier, token = signing  # allow-secret: public-key client or generated synthetic test-token helper; no credential literal
    assert verifier.verify(token()).subject == "teacher-a"
    with pytest.raises(AuthenticationError):
        verifier.verify(token()[:-4] + "xxxx")
    unsigned = jwt.encode({"sub": "teacher-a"}, key=None, algorithm="none")
    with pytest.raises(AuthenticationError):
        verifier.verify(unsigned)
    with pytest.raises(ValueError):
        TokenVerifier("http://identity.example.test", AUDIENCE, ISSUER + "/jwks")


@pytest.fixture(scope="module")
def postgres_admin():
    external = os.environ.get("EDU_TEST_ADMIN_DSN")
    if external:
        # CI service is a disposable database dedicated to this test suite.
        yield external
        return
    binaries = {name: shutil.which(name) for name in ("initdb", "pg_ctl")}
    if not all(binaries.values()):
        pytest.fail("PostgreSQL required: install native binaries or set EDU_TEST_ADMIN_DSN to a disposable test cluster")
    with tempfile.TemporaryDirectory(prefix="edu-pg-") as root:
        data = str(Path(root) / "data")
        subprocess.run([binaries["initdb"], "-D", data, "-A", "trust", "--no-locale", "--encoding=UTF8"], check=True, capture_output=True, timeout=30)
        subprocess.run([binaries["pg_ctl"], "-D", data, "-l", str(Path(root)/"postgres.log"), "-o", f"-k {root} -h '' -c shared_buffers=16MB -c max_connections=15", "-w", "start"], check=True, capture_output=True, timeout=30)
        try:
            yield f"host={root} dbname=postgres"
        finally:
            subprocess.run([binaries["pg_ctl"], "-D", data, "-m", "fast", "-w", "stop"], check=True, capture_output=True, timeout=30)


@pytest.fixture
def database(postgres_admin):
    dbname = "edu_test_" + uuid4().hex
    role = "edu_app_" + uuid4().hex
    with psycopg.connect(postgres_admin, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} ").format(sql.Identifier(dbname)))
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE").format(sql.Identifier(role)))
    settings = psycopg.conninfo.conninfo_to_dict(postgres_admin)
    settings["dbname"] = dbname
    admin_dsn = psycopg.conninfo.make_conninfo(**settings)
    migrate(admin_dsn)
    with psycopg.connect(admin_dsn) as admin:
        admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(dbname), sql.Identifier(role)))
        admin.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        admin.execute(sql.SQL("GRANT SELECT ON instructors, schema_revisions TO {}").format(sql.Identifier(role)))
        admin.execute(sql.SQL("GRANT SELECT, INSERT ON terms, courses, sections, enrollments, external_references TO {}").format(sql.Identifier(role)))
    settings["user"] = role
    # CI can use a disposable trust-auth cluster; no production credentials are loaded.
    settings.pop("password", None)
    db = Database(psycopg.conninfo.make_conninfo(**settings))
    try:
        yield db, admin_dsn
    finally:
        with psycopg.connect(postgres_admin, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(dbname)))
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def provision(admin_dsn, subject):
    owner = uuid4()
    with psycopg.connect(admin_dsn) as admin:
        admin.execute("INSERT INTO instructors (id,issuer,subject) VALUES (%s,%s,%s)", (owner, ISSUER, subject))
    return owner


@contextmanager
def clients(database, signing):
    db, admin = database
    verifier, token = signing  # allow-secret: public-key client or generated synthetic test-token helper; no credential literal
    a = provision(admin, "teacher-a")
    b = provision(admin, "teacher-b")
    with TestClient(create_backend(db, verifier)) as client:
        yield client, a, b, lambda subject: {"Authorization": "Bearer " + token(subject)}


def create_course(client, headers, title="Composition"):
    term = client.post("/v1/terms", headers=headers, json={"label": "Synthetic term", "starts_on": "2026-08-01", "ends_on": "2026-12-15"})
    assert term.status_code == 201, term.text
    course = client.post("/v1/courses", headers=headers, json={"term_id": term.json()["id"], "title": title})
    assert course.status_code == 201, course.text
    return course.json(), term.json()


def test_schema_reapply_rollback_and_unsafe_role(database):
    db, admin = database
    migrate(admin)
    db.verify()
    with pytest.raises(RuntimeError, match="unsafe_database_role"):
        Database(admin).verify()
    rollback_empty(admin)
    migrate(admin)
    db.verify()
    provision(admin, "populated")
    with pytest.raises(RuntimeError, match="rollback_requires_empty_schema"):
        rollback_empty(admin)


def test_authenticated_course_lifecycle_and_isolation(database, signing):
    with clients(database, signing) as (client, a, b, auth):
        assert client.get("/v1/terms").status_code == 401
        assert client.get("/v1/session", headers=auth("unprovisioned")).status_code == 403
        course, term = create_course(client, auth("teacher-a"))
        course_id = course["id"]
        assert client.get("/v1/courses", headers=auth("teacher-b")).json()["items"] == []
        assert client.get(f"/v1/courses/{course_id}", headers=auth("teacher-b")).status_code == 404
        assert client.post("/v1/courses", headers=auth("teacher-b"), json={"term_id": term["id"], "title": "Intrusion"}).status_code == 404
        assert client.post(f"/v1/courses/{course_id}/sections", headers=auth("teacher-b"), json={"label": "Intrusion"}).status_code == 404
        section = client.post(f"/v1/courses/{course_id}/sections", headers=auth("teacher-a"), json={"label": "A"}).json()
        base = f'/v1/courses/{course_id}/sections/{section["id"]}/enrollments'
        enrollment = client.post(base, headers=auth("teacher-a"))
        assert enrollment.status_code == 201
        assert "student_ref" in enrollment.json() and "name" not in enrollment.json()
        assert client.get(base, headers=auth("teacher-b")).status_code == 404
        assert client.get(base, headers=auth("teacher-a")).json()["items"] == [enrollment.json()]
        assert client.get("/v1/session", headers=auth("teacher-a")).json()["instructor_id"] == str(a)
        assert client.get("/v1/session", headers=auth("teacher-b")).json()["instructor_id"] == str(b)
        with psycopg.connect(database[1]) as admin:
            admin.execute("UPDATE instructors SET active=false WHERE id=%s", (a,))
        assert client.get("/v1/session", headers=auth("teacher-a")).status_code == 403


def test_cross_course_refs_constraints_and_validation(database, signing):
    db, admin_dsn = database
    with clients(database, signing) as (client, a, b, auth):
        course1, _ = create_course(client, auth("teacher-a"))
        course2, _ = create_course(client, auth("teacher-a"))
        section = client.post(f'/v1/courses/{course2["id"]}/sections', headers=auth("teacher-a"), json={"label": "B"}).json()
        wrong = f'/v1/courses/{course1["id"]}/sections/{section["id"]}/enrollments'
        assert client.post(wrong, headers=auth("teacher-a")).status_code == 404
        refs = f'/v1/courses/{course1["id"]}/references'
        payload = {"source": "aetheria", "kind": "section", "external_id": "section_1", "target_id": section["id"]}
        assert client.post(refs, headers=auth("teacher-a"), json=payload).status_code == 404
        payload.update(kind="course", target_id=course1["id"])
        assert client.post(refs, headers=auth("teacher-a"), json=payload).status_code == 201
        duplicate = client.post(refs, headers=auth("teacher-a"), json=payload)
        assert duplicate.status_code == 409 and "section_1" not in duplicate.text
        rejected = client.post("/v1/courses", headers=auth("teacher-a"), json={"term_id": str(uuid4()), "title": "x", "instructor_id": str(b)})
        assert rejected.status_code == 422 and str(b) not in rejected.text
        # The database trigger also rejects a cross-course reference if API checks are bypassed.
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with db.scoped(ISSUER, "teacher-a") as (conn, owner):
                conn.execute("INSERT INTO external_references VALUES (%s,%s,%s,'aetheria','section','bad',%s)", (uuid4(), owner, course1["id"], section["id"]))
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with db.scoped(ISSUER, "teacher-a") as (conn, owner):
                conn.execute("INSERT INTO enrollments VALUES (%s,%s,%s,%s,%s)", (uuid4(), owner, course1["id"], section["id"], uuid4()))


def test_rls_without_api_filters_and_transaction_cleanup(database, signing):
    db, admin = database
    with clients(database, signing) as (client, a, b, auth):
        course, _ = create_course(client, auth("teacher-a"))
        with db.scoped(ISSUER, "teacher-b") as (conn, owner):
            assert conn.execute("SELECT * FROM courses").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with db.scoped(ISSUER, "teacher-b") as (conn, owner):
                conn.execute("INSERT INTO terms VALUES (%s,%s,'spoof','2026-01-01','2026-12-01')", (uuid4(), a))
        with psycopg.connect(db.dsn) as conn:
            assert conn.execute("SELECT * FROM courses").fetchall() == []
            assert conn.execute("SELECT * FROM instructors").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with psycopg.connect(db.dsn) as conn:
                conn.execute("UPDATE instructors SET active=true")


def test_protected_app_denies_data_without_authentication(signing):
    verifier, _ = signing
    database = SimpleNamespace(verify=lambda: None)
    with TestClient(create_backend(database, verifier)) as client:
        assert client.get("/health").json()["real_student_data_enabled"] is False
        assert client.get("/v1/terms").status_code == 401
        assert client.post("/v1/courses", json={"title": "x"}).status_code == 401
        assert client.post("/v1/demo/intake", json={"fixture_id": "argument"}).status_code == 404
        assert client.get("/health").headers["cache-control"] == "no-store"


def test_database_transport_configuration():
    with pytest.raises(ValueError, match="explicit_database_host"):
        Database("dbname=edu")
    with pytest.raises(ValueError, match="verified_database_tls"):
        Database("host=db.example.test dbname=edu")
    with pytest.raises(ValueError, match="verified_database_tls"):
        Database("host=localhost hostaddr=192.0.2.1 dbname=edu")
    with pytest.raises(ValueError, match="verified_database_tls"):
        Database("host=/tmp,db.example.test dbname=edu")
    Database("host=db.example.test dbname=edu sslmode=verify-full")
