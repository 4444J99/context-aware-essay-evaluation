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
        self.members = set()
        self.assignment = None; self.roster_generation = 0; self.history = []

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

    def roster_assignment(self, assignment):
        return {"section_id": self.course, "roster_generation": self.roster_generation} if assignment == self.assignment else None

    def section_members(self, section):
        return {str(e) for _, e in self.members} | getattr(self, "available", set())

    def assignment_submissions(self, assignment):
        return [deepcopy(row) for row in self.rows.values() if row["assignment_id"] == assignment]

    def replace_roster(self, assignment, generation, members):
        self.roster_generation = generation; self.history.append(tuple(members))
        self.members = {(assignment, member) for member in members}

    def expected(self, assignment, enrollment):
        return (assignment, enrollment) in self.members

    def occupied(self, assignment, enrollment, submission):
        return any(r["id"] != submission and not r["excluded"] and r["assignment_id"] == assignment and r["enrollment_id"] == enrollment for r in self.rows.values())

    def save_mapping(self, row):
        self.review(row)

    def workspace(self):
        return {"assignments": [], "sections": [], "expected": [{"assignment_id": a, "enrollment_id": e} for a,e in self.members], "submissions": [self.get(r["id"]) for r in self.rows.values()]}

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
        assignment, enrollment = uuid4(), uuid4(); repo.members.add((assignment, enrollment))
        resolution_path = path + "/" + initial.json()["id"] + "/resolution"
        resolution = {"source_revision": initial.json()["source_revision"], "expected_generation": 0, "action": "mapping", "assignment_id": str(assignment), "enrollment_id": str(enrollment)}
        assert client.post(resolution_path, json=resolution).status_code == 401
        assert client.post(resolution_path, headers=headers, json={**resolution, "assignment_id": str(uuid4())}).status_code == 409
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


def test_mapping_exceptions_are_versioned_scoped_and_source_preserving(service):
    repo = MemoryRepository(); assignment, enrollment = uuid4(), uuid4(); repo.members.add((assignment, enrollment))
    first = service.ingest(repo, uuid4(), "argument"); second = service.ingest(repo, uuid4(), "argument")
    source = repo.get(first["id"])["original_object"]
    with pytest.raises(IntakeConflict, match="not_expected"):
        service.resolve(repo, first["id"], first["source_revision"], 0, "mapping", uuid4(), enrollment)
    mapped = service.resolve(repo, first["id"], first["source_revision"], 0, "mapping", assignment, enrollment)
    assert "assignment_unresolved" not in mapped["holds"] and "enrollment_unresolved" not in mapped["holds"]
    assert len(service.workspace(repo)["missing"]) == 0
    with pytest.raises(IntakeConflict, match="already_covered"):
        service.resolve(repo, second["id"], second["source_revision"], 0, "mapping", assignment, enrollment)
    with pytest.raises(IntakeConflict, match="stale"):
        service.decide(repo, first["id"], first["source_revision"], 0, {})
    excluded = service.resolve(repo, first["id"], first["source_revision"], 1, "exclude", reason="duplicate")
    assert excluded["excluded"] and len(service.workspace(repo)["missing"]) == 1
    with pytest.raises(IntakeConflict, match="excluded"):
        service.decide(repo, first["id"], first["source_revision"], 2, {})
    service.resolve(repo, second["id"], second["source_revision"], 0, "mapping", assignment, enrollment)
    with pytest.raises(IntakeConflict, match="already_covered"):
        service.resolve(repo, first["id"], first["source_revision"], 2, "restore", reason="instructor_correction")
    service.resolve(repo, second["id"], second["source_revision"], 1, "exclude", reason="duplicate")
    restored = service.resolve(repo, first["id"], first["source_revision"], 2, "restore", reason="instructor_correction")
    assert restored["state"] == "privacy_pending" and "route_unqualified" in restored["holds"]
    assert repo.get(first["id"])["original_object"] == source and repo.get(first["id"])["content_object"] is None
    pdf = service.ingest(repo, uuid4(), "pdf-held")
    excluded_pdf = service.resolve(repo, pdf["id"], pdf["source_revision"], 0, "exclude", reason="wrong_assignment")
    assert "pdf_extraction_worker_unqualified" in excluded_pdf["holds"]


def test_postgres_protected_mapping_roster_and_rls(database, signing, service):
    db, admin = database; verifier, signed = signing
    provision(admin, "mapping-a"); provision(admin, "mapping-b")
    a = {"Authorization": "Bearer " + signed("mapping-a")}; b = {"Authorization": "Bearer " + signed("mapping-b")}
    with TestClient(create_backend(db, verifier, intake_service=service)) as client:
        course, _ = create_course(client, a)
        base = f"/v1/courses/{course['id']}"
        section_response = client.post(base + "/sections", headers=a, json={"label": "Synthetic section"})
        assert section_response.status_code == 201, section_response.text
        section = section_response.json()
        member_response = client.post(base + f"/sections/{section['id']}/enrollments", headers=a, json={})
        assert member_response.status_code == 201, member_response.text
        member = member_response.json()
        created = client.post(base + "/assignments", headers=a, json={"section_id": section["id"]})
        assert created.status_code == 201, created.text
        assignment = created.json()
        first = client.post(base + "/intake", headers=a, json={"request_id": str(uuid4()), "fixture_id": "argument"}).json()
        path = base + f"/intake/{first['id']}/resolution"
        body = {"source_revision": first["source_revision"], "expected_generation": 0, "action": "mapping", "assignment_id": assignment["id"], "enrollment_id": member["id"]}
        assert client.post(path, headers=b, json=body).status_code == 404
        assert client.post(path, headers=a, json=body).status_code == 200
        assert client.post(path, headers=a, json=body).status_code == 409
        workspace = client.get(base + "/intake-workspace", headers=a).json()
        assert not workspace["missing"] and len(workspace["expected"]) == 1
        roster_path = base + f"/assignments/{assignment['id']}/roster"
        replacement = {"expected_generation": 0, "enrollment_ids": []}
        assert client.post(roster_path, headers=b, json=replacement).status_code == 404
        changed = client.post(roster_path, headers=a, json=replacement)
        assert changed.status_code == 200 and changed.json()["invalidated_submissions"] == 1
        assert client.post(roster_path, headers=a, json=replacement).status_code == 409
        history = client.get(roster_path, headers=a).json()
        assert [r["generation"] for r in history["items"]] == [1,0]
        assert history["assignment_id"] == assignment["id"] and history["course_id"] == course["id"]
        assert history["current_generation"] == 1 and history["next_before"] is None
        assert client.get(roster_path + "?before=1", headers=a).json()["items"][0]["generation"] == 0
        assert client.get(roster_path + "?before=0", headers=a).status_code == 422
        assert client.get(roster_path, headers=b).status_code == 404
        held = client.get(base + f"/intake/{first['id']}/review", headers=a).json()
        assert held["review_generation"] == 2 and "roster_membership_removed" in held["holds"]
        assert client.post(roster_path, headers=a, json={"expected_generation": 1, "enrollment_ids": [member["id"]]}).status_code == 200
        with psycopg.connect(admin) as conn:
            assert conn.execute("SELECT count(*) FROM assignment_roster_versions").fetchone()[0] == 3
        assert client.get(base + "/intake-workspace", headers=b).status_code == 404
        with db.scoped(verifier.issuer, "mapping-b") as (conn, _):
            assert conn.execute("SELECT count(*) AS n FROM assignments").fetchone()["n"] == 0
            assert conn.execute("SELECT count(*) AS n FROM assignment_enrollments").fetchone()["n"] == 0
            assert conn.execute("SELECT count(*) AS n FROM assignment_roster_versions").fetchone()["n"] == 0


def test_roster_updates_preserve_matches_invalidate_review_and_hold_removed_members(service):
    repo = MemoryRepository(); assignment, enrollment, added = uuid4(), uuid4(), uuid4()
    repo.assignment = assignment; repo.members.add((assignment, enrollment)); repo.available = {str(added), str(enrollment)}
    first = service.ingest(repo, uuid4(), "argument")
    service.resolve(repo, first["id"], first["source_revision"], 0, "mapping", assignment, enrollment)
    view = service.review_view(repo, first["id"])
    service.decide(repo, first["id"], first["source_revision"], 1, {p["id"]: "retain" for p in view["passages"]})
    original = repo.get(first["id"])["original_object"]
    with pytest.raises(IntakeConflict, match="outside_section"):
        service.update_roster(repo, assignment, 0, [uuid4()])
    result = service.update_roster(repo, assignment, 0, [added])
    assert result["roster_generation"] == 1 and result["invalidated_submissions"] == 1
    row = repo.get(first["id"])
    assert row["original_object"] == original and row["content_object"] is None and row["review_generation"] == 3
    assert row["enrollment_id"] == enrollment and "roster_membership_removed" in row["holds"]
    assert len(service.workspace(repo)["missing"]) == 1
    with pytest.raises(IntakeConflict, match="stale"):
        service.update_roster(repo, assignment, 0, [enrollment])
    reviewed = service.decide(repo, first["id"], first["source_revision"], 3, {p["id"]: "retain" for p in view["passages"]})
    assert "roster_membership_removed" in reviewed["holds"]
    service.update_roster(repo, assignment, 1, [enrollment, added])
    assert "roster_membership_removed" not in repo.get(first["id"])["holds"]
    assert repo.get(first["id"])["state"] == "privacy_pending" and len(repo.history) == 2


def test_roster_history_repository_scopes_and_pages_without_source_content():
    from essay_evaluation.intake import SqlIntakeRepository
    from unittest.mock import Mock
    owner, course, assignment = uuid4(), uuid4(), uuid4()
    conn = Mock(); rows = [{"generation": n, "enrollment_ids": [], "created_at": "2026-10-13T00:00:00Z"} for n in range(200,99,-1)]
    conn.execute.return_value.fetchall.return_value = rows
    repo = SqlIntakeRepository(conn, owner, course)
    repo.require_course = Mock(); repo.roster_assignment = Mock(return_value={"roster_generation": 201})
    result = repo.roster_history(assignment, 201)
    assert len(result["items"]) == 100 and result["next_before"] == 101
    assert result["assignment_id"] == assignment and result["course_id"] == course
    sql, parameters = conn.execute.call_args.args
    assert "generation <" in sql and parameters == (assignment, course, owner, 201, 201)
    assert "original_object" not in str(result)
    repo.roster_assignment.return_value = None
    with pytest.raises(LookupError): repo.roster_history(assignment)
