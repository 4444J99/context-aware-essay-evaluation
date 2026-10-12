"""Versioned PostgreSQL schema and transaction-local authorization context."""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

MIGRATIONS = Path(__file__).with_name("migrations")
REVISION = "001_scope"


def migration_digest() -> str:
    return sha256((MIGRATIONS / f"{REVISION}.up.sql").read_bytes()).hexdigest()


def migrate(dsn: str) -> None:
    """Run as a migration administrator, never as the request-serving role."""
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(38218571)")
        conn.execute("CREATE TABLE IF NOT EXISTS schema_revisions (revision text PRIMARY KEY, checksum text NOT NULL)")
        rows = conn.execute("SELECT revision, checksum FROM schema_revisions").fetchall()
        if rows:
            if rows != [(REVISION, migration_digest())]:
                raise RuntimeError("schema_revision_mismatch")
            return
        conn.execute((MIGRATIONS / f"{REVISION}.up.sql").read_text())
        conn.execute("INSERT INTO schema_revisions VALUES (%s, %s)", (REVISION, migration_digest()))


def rollback_empty(dsn: str) -> None:
    """Rollback rehearsal only: refuse to remove any populated application schema."""
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(38218571)")
        # Fail rather than let RLS hide populated records from the administrator.
        conn.execute("SET LOCAL row_security = off")
        # Lock against concurrent inserts before checking emptiness.
        conn.execute("LOCK TABLE instructors, terms, courses, sections, enrollments, external_references IN ACCESS EXCLUSIVE MODE")
        count = conn.execute("SELECT (SELECT count(*) FROM instructors) + (SELECT count(*) FROM terms)").fetchone()[0]
        if count:
            raise RuntimeError("rollback_requires_empty_schema")
        conn.execute((MIGRATIONS / f"{REVISION}.down.sql").read_text())
        conn.execute("DELETE FROM schema_revisions WHERE revision = %s", (REVISION,))


class Database:
    def __init__(self, dsn: str):
        settings = psycopg.conninfo.conninfo_to_dict(dsn)
        host = settings.get("host", "")
        local = all(part.startswith("/") or part in {"127.0.0.1", "::1", "localhost"} for part in host.split(","))
        if not host:
            raise ValueError("explicit_database_host_required")
        if (not local or settings.get("hostaddr")) and settings.get("sslmode") != "verify-full":
            raise ValueError("verified_database_tls_required")
        self.dsn = dsn

    def verify(self) -> None:
        with psycopg.connect(self.dsn, connect_timeout=5) as conn:
            role = conn.execute("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()
            if any(role):
                raise RuntimeError("unsafe_database_role")
            if conn.execute("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname='public' AND pg_has_role(current_user, tableowner, 'USAGE'))").fetchone()[0]:
                raise RuntimeError("runtime_role_must_not_own_tables")
            protected = conn.execute("SELECT count(*) FROM pg_class JOIN pg_namespace ON pg_namespace.oid=pg_class.relnamespace WHERE nspname='public' AND relname = ANY(%s) AND relrowsecurity AND relforcerowsecurity", (["instructors", "terms", "courses", "sections", "enrollments", "external_references"],)).fetchone()[0]
            if protected != 6:
                raise RuntimeError("schema_row_security_required")
            rows = conn.execute("SELECT revision, checksum FROM schema_revisions").fetchall()
            if rows != [(REVISION, migration_digest())]:
                raise RuntimeError("schema_revision_mismatch")

    @contextmanager
    def scoped(self, issuer: str, subject: str):
        with psycopg.connect(self.dsn, connect_timeout=5, row_factory=dict_row) as conn:
            conn.execute("SET LOCAL statement_timeout = '5s'")
            conn.execute("SELECT set_config('edu.issuer', %s, true), set_config('edu.subject', %s, true)", (issuer, subject))
            row = conn.execute("SELECT id FROM instructors WHERE issuer=%s AND subject=%s AND active", (issuer, subject)).fetchone()
            if row is None:
                raise PermissionError("instructor_not_provisioned")
            owner = UUID(str(row["id"]))
            conn.execute("SELECT set_config('edu.instructor_id', %s, true)", (str(owner),))
            yield conn, owner
