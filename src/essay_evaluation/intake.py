"""Protected synthetic intake orchestration. Authorization/transaction supplied by backend."""
import base64
from io import BytesIO
from uuid import uuid4
import zipfile
from xml.sax.saxutils import escape

from cryptography.exceptions import InvalidTag

from .contextual_privacy import plan_review, finalize_review
from .extraction import extract, ExtractionHold
from .fixtures import FIXTURES
from .durable_vault import DomainKeyRing

QUALIFICATION_HOLDS = ["enrollment_unresolved", "assignment_unresolved", "synthetic_only", "parser_unqualified", "route_unqualified", "release_unavailable"]


class IntakeConflict(ValueError):
    pass


class IntakeStorageError(RuntimeError):
    pass


def fixture_bytes(fixture_id):
    if fixture_id == "pdf-held":
        return b"%PDF synthetic fixture, not a student document", "pdf", ()
    key = "argument" if fixture_id == "docx-argument" else fixture_id
    if key not in FIXTURES:
        raise ValueError("fixture_unknown")
    fixture = FIXTURES[key]
    if fixture_id != "docx-argument":
        return fixture["text"].encode(), "txt", (fixture["name"],)
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        paragraphs = "".join("<w:p><w:r><w:t>" + escape(p) + "</w:t></w:r></w:p>" for p in fixture["text"].split("\n"))
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + paragraphs + '</w:body></w:document>')
    return output.getvalue(), "docx", (fixture["name"],)


class SqlIntakeRepository:
    def __init__(self, conn, owner, course):
        self.conn, self.owner, self.course = conn, owner, course

    def require_course(self):
        if self.conn.execute("SELECT id FROM courses WHERE id=%s AND instructor_id=%s", (self.course, self.owner)).fetchone() is None:
            raise LookupError("record_not_found")
        self.conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"edu-intake:{self.owner}:{self.course}",))

    def find_request(self, request_id):
        return self.conn.execute("SELECT * FROM intake_submissions WHERE instructor_id=%s AND course_id=%s AND request_id=%s", (self.owner, self.course, request_id)).fetchone()

    def get(self, submission, lock=False):
        return self.conn.execute("SELECT * FROM intake_submissions WHERE id=%s AND instructor_id=%s AND course_id=%s" + (" FOR UPDATE" if lock else ""), (submission, self.owner, self.course)).fetchone()

    def insert(self, row):
        self.conn.execute("INSERT INTO intake_submissions (id,instructor_id,course_id,request_id,fixture_id,source_revision,original_object,content_object,review_generation,state,holds) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", tuple(row[k] for k in ("id", "instructor_id", "course_id", "request_id", "fixture_id", "source_revision", "original_object", "content_object", "review_generation", "state", "holds")))

    def review(self, row):
        self.conn.execute("UPDATE intake_submissions SET content_object=%s,review_generation=%s,state=%s,holds=%s WHERE id=%s AND instructor_id=%s AND course_id=%s", (row["content_object"], row["review_generation"], row["state"], row["holds"], row["id"], self.owner, self.course))

    def save_mapping(self, row):
        self.conn.execute("UPDATE intake_submissions SET assignment_id=%s,enrollment_id=%s,excluded=%s WHERE id=%s AND instructor_id=%s AND course_id=%s", (row["assignment_id"], row["enrollment_id"], row["excluded"], row["id"], self.owner, self.course))
        self.review(row)

    def expected(self, assignment, enrollment):
        return self.conn.execute("SELECT enrollment_id FROM assignment_enrollments WHERE assignment_id=%s AND enrollment_id=%s AND course_id=%s AND instructor_id=%s AND active", (assignment, enrollment, self.course, self.owner)).fetchone() is not None

    def occupied(self, assignment, enrollment, submission):
        return self.conn.execute("SELECT id FROM intake_submissions WHERE assignment_id=%s AND enrollment_id=%s AND id<>%s AND NOT excluded AND course_id=%s AND instructor_id=%s", (assignment, enrollment, submission, self.course, self.owner)).fetchone() is not None

    def workspace(self):
        self.require_course()
        result = {}
        queries = {
            "assignments": "SELECT id,section_id,label,roster_generation FROM assignments",
            "expected": "SELECT assignment_id,enrollment_id FROM assignment_enrollments WHERE active",
            "submissions": "SELECT * FROM intake_submissions",
            "sections": "SELECT id,label FROM sections",
            "enrollments": "SELECT id,section_id FROM enrollments",
        }
        for key, query in queries.items():
            rows = self.conn.execute(query + (" AND" if " WHERE" in query else " WHERE") + " course_id=%s AND instructor_id=%s ORDER BY " + ("assignment_id,enrollment_id" if key == "expected" else "id") + " LIMIT 1001", (self.course, self.owner)).fetchall()
            if len(rows) > 1000:
                raise IntakeConflict("workspace_size_limit")
            result[key] = rows
        return result

    def create_assignment(self, section, label):
        self.require_course()
        if self.conn.execute("SELECT id FROM sections WHERE id=%s AND course_id=%s AND instructor_id=%s", (section, self.course, self.owner)).fetchone() is None:
            raise LookupError("record_not_found")
        members = self.conn.execute("SELECT id FROM enrollments WHERE section_id=%s AND course_id=%s AND instructor_id=%s ORDER BY id LIMIT 1001", (section, self.course, self.owner)).fetchall()
        if not members or len(members) > 1000:
            raise IntakeConflict("assignment_roster_required_or_too_large")
        assignment = uuid4()
        self.conn.execute("INSERT INTO assignments(id,instructor_id,course_id,section_id,label) VALUES (%s,%s,%s,%s,%s)", (assignment, self.owner, self.course, section, label))
        for member in members:
            self.conn.execute("INSERT INTO assignment_enrollments(assignment_id,enrollment_id,course_id,instructor_id) VALUES (%s,%s,%s,%s)", (assignment, member["id"], self.course, self.owner))
        self.conn.execute("INSERT INTO assignment_roster_versions(assignment_id,course_id,instructor_id,generation,enrollment_ids) VALUES (%s,%s,%s,0,%s)", (assignment, self.course, self.owner, [m["id"] for m in members]))
        return {"id": assignment, "section_id": section, "label": label, "roster_generation": 0}

    def roster_assignment(self, assignment):
        return self.conn.execute("SELECT * FROM assignments WHERE id=%s AND course_id=%s AND instructor_id=%s FOR UPDATE", (assignment, self.course, self.owner)).fetchone()

    def section_members(self, section):
        rows = self.conn.execute("SELECT id FROM enrollments WHERE section_id=%s AND course_id=%s AND instructor_id=%s ORDER BY id LIMIT 1001", (section, self.course, self.owner)).fetchall()
        if len(rows) > 1000:
            raise IntakeConflict("roster_size_limit")
        return {str(row["id"]) for row in rows}

    def replace_roster(self, assignment, generation, members):
        self.conn.execute("UPDATE assignment_enrollments SET active=false WHERE assignment_id=%s AND course_id=%s AND instructor_id=%s", (assignment, self.course, self.owner))
        for enrollment in members:
            self.conn.execute("INSERT INTO assignment_enrollments(assignment_id,enrollment_id,course_id,instructor_id) VALUES (%s,%s,%s,%s) ON CONFLICT(assignment_id,enrollment_id) DO UPDATE SET active=true", (assignment, enrollment, self.course, self.owner))
        self.conn.execute("UPDATE assignments SET roster_generation=%s WHERE id=%s AND course_id=%s AND instructor_id=%s", (generation, assignment, self.course, self.owner))
        self.conn.execute("INSERT INTO assignment_roster_versions(assignment_id,course_id,instructor_id,generation,enrollment_ids) VALUES (%s,%s,%s,%s,%s)", (assignment, self.course, self.owner, generation, members))

    def assignment_submissions(self, assignment):
        rows = self.conn.execute("SELECT * FROM intake_submissions WHERE assignment_id=%s AND course_id=%s AND instructor_id=%s ORDER BY id LIMIT 1001 FOR UPDATE", (assignment, self.course, self.owner)).fetchall()
        if len(rows) > 1000:
            raise IntakeConflict("workspace_size_limit")
        return rows

    def roster_history(self, assignment, before=None):
        self.require_course()
        current = self.roster_assignment(assignment)
        if current is None:
            raise LookupError("record_not_found")
        rows = self.conn.execute("SELECT generation,enrollment_ids,created_at FROM assignment_roster_versions WHERE assignment_id=%s AND course_id=%s AND instructor_id=%s AND (%s::integer IS NULL OR generation < %s) ORDER BY generation DESC LIMIT 101", (assignment, self.course, self.owner, before, before)).fetchall()
        page = rows[:100]
        return {"assignment_id": assignment, "course_id": self.course, "current_generation": current["roster_generation"],
                "items": page, "older_versions_available": len(rows) > 100,
                "next_before": page[-1]["generation"] if len(rows) > 100 else None}

    def audit(self, row, action, private_object):
        self.conn.execute("INSERT INTO intake_events (id,instructor_id,course_id,submission_id,generation,action,private_object) VALUES (%s,%s,%s,%s,%s,%s,%s)", (uuid4(), self.owner, self.course, row["id"], row["review_generation"], action, private_object))


class IntakeService:
    def __init__(self, identity_vault, content_vault):
        if identity_vault.domain != "identity" or content_vault.domain != "content":
            raise ValueError("separate_intake_vault_domains_required")
        if isinstance(identity_vault.provider, DomainKeyRing) and isinstance(content_vault.provider, DomainKeyRing):
            if set(identity_vault.provider.keys.values()) & set(content_vault.provider.keys.values()):
                raise ValueError("identity_and_content_keys_must_differ")
        self.identity, self.content = identity_vault, content_vault

    @staticmethod
    def view(row):
        return {k: row[k] for k in ("id", "course_id", "source_revision", "review_generation", "state", "holds", "assignment_id", "enrollment_id", "excluded")}

    @staticmethod
    def vault_call(vault, method, *args):
        try:
            return getattr(vault, method)(*args)
        except (OSError, ValueError, InvalidTag, KeyError, TypeError):
            raise IntakeStorageError("intake_storage_unavailable") from None

    def binding(self, repo, row):
        return {"instructor_id": str(repo.owner), "course_id": str(repo.course), "submission_id": str(row["id"]), "source_revision": str(row["source_revision"])}

    def ingest(self, repo, request_id, fixture_id):
        repo.require_course()  # Scoped transaction advisory lock serializes request-key admission.
        existing = repo.find_request(request_id)
        if existing:
            if existing["fixture_id"] != fixture_id:
                raise IntakeConflict("idempotency_conflict")
            return self.view(existing)
        data, kind, identifiers = fixture_bytes(fixture_id)
        row = {"id": uuid4(), "instructor_id": repo.owner, "course_id": repo.course, "request_id": request_id,
               "fixture_id": fixture_id, "source_revision": uuid4(), "review_generation": 0, "content_object": None, "assignment_id": None, "enrollment_id": None, "excluded": False}
        try:
            extracted = extract(data, kind)
            row.update(state="privacy_pending", holds=["contextual_review_required"] + QUALIFICATION_HOLDS)
            text, paragraphs = extracted.text, extracted.paragraphs
        except ExtractionHold as error:
            row.update(state="extraction_held", holds=[str(error)] + QUALIFICATION_HOLDS)
            text, paragraphs = None, ()
        private = {**self.binding(repo, row), "format": kind, "source_bytes": base64.b64encode(data).decode(),
                   "normalized_text": text, "paragraphs": paragraphs, "known_identifiers": identifiers, "synthetic": True}
        row["original_object"] = self.vault_call(self.identity, "put", str(repo.course), private)
        repo.insert(row)
        repo.audit(row, "created", row["original_object"])
        return self.view(row)

    def source(self, repo, row):
        source = self.vault_call(self.identity, "get", str(repo.course), str(row["original_object"]))
        if any(source.get(key) != value for key, value in self.binding(repo, row).items()) or source.get("synthetic") is not True:
            raise IntakeStorageError("intake_storage_binding_invalid")
        return source

    def review_view(self, repo, submission):
        row = repo.get(submission)
        if row is None:
            raise LookupError("record_not_found")
        source = self.source(repo, row)
        if row["state"] == "extraction_held":
            return {**self.view(row), "passages": []}
        plan = plan_review(source["normalized_text"], str(repo.course), str(row["id"]), tuple(source["known_identifiers"]))
        # Original passages are restricted to the authorized instructor review response.
        return {**self.view(row), "passages": [{"id": p.id, "start": p.start, "end": p.end, "flags": p.flags, "text": plan.source[p.start:p.end]} for p in plan.passages]}

    def decide(self, repo, submission, source_revision, generation, decisions):
        repo.require_course()
        row = repo.get(submission, lock=True)
        if row is None:
            raise LookupError("record_not_found")
        if str(row["source_revision"]) != str(source_revision) or row["review_generation"] != generation:
            raise IntakeConflict("review_version_stale")
        if row["excluded"]:
            raise IntakeConflict("submission_excluded")
        if row["state"] == "extraction_held":
            raise IntakeConflict("extraction_held")
        source = self.source(repo, row)
        plan = plan_review(source["normalized_text"], str(repo.course), str(row["id"]), tuple(source["known_identifiers"]))
        result = finalize_review(plan, source["normalized_text"], str(repo.course), str(row["id"]), str(repo.owner), decisions)
        updated = {**row, "review_generation": generation + 1, "content_object": None,
                   "state": "privacy_reviewed" if result.document else "privacy_pending",
                   "holds": list(result.holds) + self.mapping_holds(row)}
        private = {**self.binding(repo, row), "reviewer_id": str(repo.owner), "generation": generation + 1,
                   "decisions": decisions, "source_version": plan.version,
                   "replacements": [vars(r) for r in result.document.replacements] if result.document else []}
        audit_id = self.vault_call(self.identity, "put", str(repo.course), private)
        if result.document:
            updated["content_object"] = self.vault_call(self.content, "put", str(repo.course),
                {**self.binding(repo, row), "generation": generation + 1, "text": result.document.text, "synthetic": True})
        repo.review(updated)
        repo.audit(updated, "privacy_review", audit_id)
        return self.view(updated)

    @staticmethod
    def mapping_holds(row):
        return (["roster_membership_removed"] if "roster_membership_removed" in row["holds"] else []) + [h for h in QUALIFICATION_HOLDS if row["assignment_id"] is None or h not in ("assignment_unresolved", "enrollment_unresolved")] + (["submission_excluded"] if row["excluded"] else [])

    def workspace(self, repo):
        result = repo.workspace()
        result["submissions"] = [self.view(row) for row in result["submissions"]]
        covered = {(str(row["assignment_id"]), str(row["enrollment_id"])) for row in result["submissions"] if not row["excluded"] and row["assignment_id"]}
        result["missing"] = [row for row in result["expected"] if (str(row["assignment_id"]), str(row["enrollment_id"])) not in covered]
        return result

    def resolve(self, repo, submission, source_revision, generation, action, assignment=None, enrollment=None, reason=None):
        repo.require_course()
        row = repo.get(submission, lock=True)
        if row is None:
            raise LookupError("record_not_found")
        if str(row["source_revision"]) != str(source_revision) or row["review_generation"] != generation:
            raise IntakeConflict("review_version_stale")
        updated = {**row, "review_generation": generation + 1, "content_object": None}
        if action == "mapping":
            if assignment is None or enrollment is None or not repo.expected(assignment, enrollment):
                raise IntakeConflict("assignment_enrollment_not_expected")
            updated.update(assignment_id=assignment, enrollment_id=enrollment, holds=[h for h in row["holds"] if h != "roster_membership_removed"])
        elif action in ("exclude", "restore") and reason in ("duplicate", "wrong_assignment", "withdrawn", "instructor_correction"):
            updated["excluded"] = action == "exclude"
        else:
            raise ValueError("resolution_invalid")
        if not updated["excluded"] and updated["assignment_id"] and repo.occupied(updated["assignment_id"], updated["enrollment_id"], submission):
            raise IntakeConflict("enrollment_already_covered")
        updated["state"] = "extraction_held" if row["state"] == "extraction_held" else "privacy_pending"
        extraction = [h for h in row["holds"] if h not in QUALIFICATION_HOLDS and h not in ("submission_excluded", "roster_membership_removed")] if row["state"] == "extraction_held" else ["contextual_review_required"]
        updated["holds"] = list(dict.fromkeys(extraction + self.mapping_holds(updated)))
        audit = {**self.binding(repo, row), "reviewer_id": str(repo.owner), "generation": generation + 1,
                 "action": action, "reason": reason, "assignment_id": str(updated["assignment_id"]) if updated["assignment_id"] else None,
                 "enrollment_id": str(updated["enrollment_id"]) if updated["enrollment_id"] else None}
        private = self.vault_call(self.identity, "put", str(repo.course), audit)
        repo.save_mapping(updated)
        repo.audit(updated, action, private)
        return self.view(updated)

    def update_roster(self, repo, assignment, generation, members):
        repo.require_course()
        current = repo.roster_assignment(assignment)
        if current is None:
            raise LookupError("record_not_found")
        if current["roster_generation"] != generation:
            raise IntakeConflict("roster_version_stale")
        if len(members) != len(set(map(str, members))) or not set(map(str, members)) <= repo.section_members(current["section_id"]):
            raise IntakeConflict("roster_enrollment_outside_section")
        rows = repo.assignment_submissions(assignment)
        # Validate and lock the bounded set before publishing any ciphertext or metadata.
        if any(row["review_generation"] >= 2_147_483_647 for row in rows):
            raise IntakeConflict("review_generation_exhausted")
        for row in rows:
            updated = {**row, "review_generation": row["review_generation"] + 1, "content_object": None}
            updated["state"] = "extraction_held" if row["state"] == "extraction_held" else "privacy_pending"
            updated["holds"] = [h for h in row["holds"] if h not in ("roster_membership_removed", "contextual_review_required")]
            if str(row["enrollment_id"]) not in set(map(str, members)):
                updated["holds"].append("roster_membership_removed")
            if updated["state"] != "extraction_held":
                updated["holds"].append("contextual_review_required")
            audit = {**self.binding(repo, row), "reviewer_id": str(repo.owner), "generation": updated["review_generation"],
                     "reason": "assignment_roster_update", "roster_generation": generation + 1}
            private = self.vault_call(self.identity, "put", str(repo.course), audit)
            repo.save_mapping(updated)
            repo.audit(updated, "mapping", private)
        repo.replace_roster(assignment, generation + 1, members)
        return {"id": assignment, "roster_generation": generation + 1, "invalidated_submissions": len(rows)}
