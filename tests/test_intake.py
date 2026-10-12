from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4, UUID

from fastapi.testclient import TestClient
import psycopg
import pytest

from essay_evaluation.backend import create_backend
from essay_evaluation.durable_vault import DurableVault, DomainKeyRing
from essay_evaluation.intake import IntakeService, IntakeConflict, IntakeStorageError
from test_backend import signing, database, postgres_admin, provision, create_course


class MemoryRepository:
    """Service contract double, explicitly not PostgreSQL/RLS evidence."""
    def __init__(self, owner=None, course=None):
        self.owner, self.course = owner or uuid4(), course or uuid4()
        self.rows, self.events = {}, []

    def require_course(self):
        pass

    def find_request(self, request_id):
        return next((r for r in self.rows.values() if r["request_id"] == request_id and r["course_id"] == self.course and r["instructor_id"] == self.owner), None)

    def get(self, submission, lock=False):
        row = self.rows.get(str(submission))
        return deepcopy(row) if row and row["course_id"] == self.course and row["instructor_id"] == self.owner else None

    def insert(self, row):
        self.rows[str(row["id"])] = deepcopy(row)

    def review(self, row):
        self.rows[str(row["id"])] = deepcopy(row)

    def audit(self, row, action, private_object):
        self.events.append((row["id"], row["review_generation"], action, private_object))


@pytest.fixture
def service(tmp_path):
    identity = DurableVault(tmp_path / "identity", DomainKeyRing("identity", "v1", {"v1": b"i" * 32}))
    content = DurableVault(tmp_path / "content", DomainKeyRing("content", "v1", {"v1": b"c" * 32}))
    return IntakeService(identity, content)


@pytest.mark.parametrize("fixture", ["argument", "literary", "contextual", "docx-argument"])
def test_scoped_intake_persistent_originals_review_and_holds(service, fixture):
    repo = MemoryRepository(); request = uuid4()
    initial = service.ingest(repo, request, fixture)
    assert initial["state"] == "privacy_pending" and initial["review_generation"] == 0
    assert service.ingest(repo, request, fixture) == initial and len(repo.events) == 1
    with pytest.raises(IntakeConflict, match="idempotency_conflict"):
        service.ingest(repo, request, "pdf-held")
    restarted = IntakeService(DurableVault(service.identity.root, service.identity.provider), DurableVault(service.content.root, service.content.provider))
    view = restarted.review_view(repo, initial["id"])
    assert view["passages"] and "original_object" not in view
    decisions = {p["id"]: "redact" if p["flags"] else "retain" for p in view["passages"]}
    reviewed = restarted.decide(repo, initial["id"], view["source_revision"], 0, decisions)
    assert reviewed["state"] == "privacy_reviewed" and reviewed["review_generation"] == 1
    assert "route_unqualified" in reviewed["holds"] and "synthetic_only" in reviewed["holds"]
    row = repo.get(initial["id"])
    processed = service.content.get(str(repo.course), row["content_object"])
    assert "@example.invalid" not in processed["text"]
    assert "Morgan Example" not in processed["text"] and "Taylor Fiction" not in processed["text"]
    assert len(repo.events) == 2
    audit = service.identity.get(str(repo.course), repo.events[-1][3])
    assert audit["reviewer_id"] == str(repo.owner) and audit["generation"] == 1
    assert "text" not in audit
    with pytest.raises(IntakeConflict, match="review_version_stale"):
        service.decide(repo, initial["id"], view["source_revision"], 0, decisions)
    with pytest.raises(IntakeConflict, match="review_version_stale"):
        service.decide(repo, initial["id"], uuid4(), 1, decisions)


def test_pending_review_clears_processed_pointer_and_pdf_cannot_be_approved(service):
    repo = MemoryRepository(); initial = service.ingest(repo, uuid4(), "argument")
    view = service.review_view(repo, initial["id"])
    decisions = {p["id"]: "retain" for p in view["passages"]}
    service.decide(repo, initial["id"], view["source_revision"], 0, decisions)
    result = service.decide(repo, initial["id"], view["source_revision"], 1, {})
    assert result["state"] == "privacy_pending" and repo.get(initial["id"])["content_object"] is None
    pdf = service.ingest(repo, uuid4(), "pdf-held")
    assert pdf["state"] == "extraction_held" and "pdf_extraction_worker_unqualified" in pdf["holds"]
    assert service.review_view(repo, pdf["id"])["passages"] == []
    with pytest.raises(IntakeConflict, match="extraction_held"):
        service.decide(repo, pdf["id"], pdf["source_revision"], 0, {})


def test_cross_scope_and_swapped_vault_reference_fail_closed(service):
    repo = MemoryRepository(); first = service.ingest(repo, uuid4(), "argument"); second = service.ingest(repo, uuid4(), "literary")
    repo.rows[str(first["id"])]["original_object"] = repo.rows[str(second["id"])]["original_object"]
    with pytest.raises(IntakeStorageError, match="binding"):
        service.review_view(repo, first["id"])
    repo.owner = uuid4()
    with pytest.raises(LookupError):
        service.review_view(repo, second["id"])


def test_vault_failure_does_not_publish_metadata(service, monkeypatch):
    repo = MemoryRepository()
    monkeypatch.setattr(service.identity, "put", lambda *args: (_ for _ in ()).throw(OSError("private storage path")))
    with pytest.raises(IntakeStorageError, match="intake_storage_unavailable"):
        service.ingest(repo, uuid4(), "argument")
    assert not repo.rows and not repo.events


def test_authenticated_route_wiring_and_unconfigured_hold(service, signing, monkeypatch):
    verifier, token = signing  # allow-secret: generated synthetic JWT signing helper, no credential literal
    owner, course = uuid4(), uuid4(); repo = MemoryRepository(owner, course)
    @contextmanager
    def scoped(issuer, subject):
        if subject != "instructor":
            raise PermissionError()
        yield None, owner
    db = SimpleNamespace(verify=lambda: None, scoped=scoped)
    import essay_evaluation.intake_api as module
    def repository(conn, actual_owner, actual_course):
        assert actual_owner == owner
        if actual_course != course:
            raise LookupError()
        return repo
    # Authorization is real JWT + scoped dependency; persistence is a contract double.
    monkeypatch.setattr(module, "SqlIntakeRepository", repository)
    path = f"/v1/courses/{course}/intake"
    headers = {"Authorization": "Bearer " + token("instructor")}
    with TestClient(create_backend(db, verifier, intake_service=service)) as client:
        assert client.post(path, json={"request_id": str(uuid4()), "fixture_id": "argument"}).status_code == 401
        assert client.post(path, headers=headers, content=b"x" * 65537).status_code == 413
        initial = client.post(path, headers=headers, json={"request_id": str(uuid4()), "fixture_id": "argument"})
        assert initial.status_code == 201
        view_path = path + "/" + initial.json()["id"] + "/review"
        view = client.get(view_path, headers=headers).json()
        assert client.get(view_path, headers=headers).headers["cache-control"] == "no-store"
        decisions = {str(p["id"]): "retain" for p in view["passages"]}
        body = {"source_revision": view["source_revision"], "expected_generation": 0, "decisions": decisions}
        assert client.post(view_path, headers=headers, json=body).status_code == 200
        assert client.post(view_path, headers=headers, json=body).status_code == 409
        unsafe = client.post(path, headers=headers, json={"request_id": str(uuid4()), "fixture_id": "argument", "private-input-name": "private value"})
        assert unsafe.status_code == 422 and "private" not in unsafe.text
    with TestClient(create_backend(db, verifier)) as client:
        assert client.post(path, headers=headers, json={"request_id": str(uuid4()), "fixture_id": "argument"}).status_code == 503


def test_postgres_protected_intake_isolation_and_transaction(database, signing, service):
    db, admin = database; verifier, token = signing  # allow-secret: generated synthetic JWT helper, no credential literal
    provision(admin, "teacher-a"); provision(admin, "teacher-b")
    a = {"Authorization": "Bearer " + token("teacher-a")}; b = {"Authorization": "Bearer " + token("teacher-b")}
    with TestClient(create_backend(db, verifier, intake_service=service)) as client:
        course, _ = create_course(client, a)
        path = f"/v1/courses/{course['id']}/intake"; request = str(uuid4())
        body = {"request_id": request, "fixture_id": "docx-argument"}
        first = client.post(path, headers=a, json=body)
        assert first.status_code == 201, first.text
        assert client.post(path, headers=a, json=body).json() == first.json()
        view_path = path + "/" + first.json()["id"] + "/review"
        assert client.get(view_path, headers=b).status_code == 404
        assert client.post(path, headers=b, json=body).status_code == 404
        view = client.get(view_path, headers=a).json()
        review = {"source_revision": view["source_revision"], "expected_generation": 0, "decisions": {str(p["id"]): "retain" for p in view["passages"]}}
        assert client.post(view_path, headers=a, json=review).status_code == 200
        assert client.post(view_path, headers=a, json=review).status_code == 409
        with psycopg.connect(admin) as conn:
            assert conn.execute("SELECT count(*) FROM intake_events").fetchone()[0] == 2
        with db.scoped(verifier.issuer, "teacher-b") as (conn, _):
            assert conn.execute("SELECT count(*) AS count FROM intake_submissions").fetchone()["count"] == 0
            assert conn.execute("SELECT count(*) AS count FROM intake_events").fetchone()["count"] == 0
        # Database failure after vault publication must roll back metadata and audit atomically.
        with psycopg.connect(admin) as conn:
            from psycopg import sql
            role = psycopg.conninfo.conninfo_to_dict(db.dsn)["user"]
            conn.execute(sql.SQL("REVOKE INSERT ON intake_events FROM {}").format(sql.Identifier(role)))
        assert client.post(path, headers=a, json={"request_id": str(uuid4()), "fixture_id": "argument"}).status_code == 503
        with psycopg.connect(admin) as conn:
            assert conn.execute("SELECT count(*) FROM intake_submissions").fetchone()[0] == 1


def test_intake_rejects_same_wrapping_keys_across_domains(tmp_path):
    keys = {"v1": b"s" * 32}
    identity = DurableVault(tmp_path / "identity", DomainKeyRing("identity", "v1", keys))
    content = DurableVault(tmp_path / "content", DomainKeyRing("content", "v1", keys))
    with pytest.raises(ValueError, match="keys_must_differ"):
        IntakeService(identity, content)
