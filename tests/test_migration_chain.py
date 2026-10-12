"""Migration control flow only; SQL execution is covered by pending PostgreSQL tests."""
import pytest
from essay_evaluation import database as module


class Connection:
    def __init__(self, rows):
        self.rows = list(rows); self.statements = []
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, query, params=None):
        self.statements.append((query, params))
        if query.startswith("INSERT INTO schema_revisions"):
            self.rows.append(params)
        return self
    def fetchall(self): return self.rows


def test_upgrade_only_applies_missing_revision(monkeypatch):
    conn = Connection([("001_scope", module.migration_digest("001_scope"))])
    monkeypatch.setattr(module.psycopg, "connect", lambda *a, **k: conn)
    module.migrate("synthetic-dsn")
    assert conn.rows == [(r, module.migration_digest(r)) for r in module.REVISIONS]
    assert any("CREATE TABLE intake_submissions" in query for query, _ in conn.statements)
    assert not any("CREATE TABLE instructors" in query for query, _ in conn.statements)


def test_current_revision_is_repeat_safe(monkeypatch):
    conn = Connection([(r, module.migration_digest(r)) for r in module.REVISIONS])
    monkeypatch.setattr(module.psycopg, "connect", lambda *a, **k: conn)
    module.migrate("synthetic-dsn")
    assert not any(query.startswith("INSERT INTO schema_revisions") for query, _ in conn.statements)


@pytest.mark.parametrize("rows", [[("001_scope", "tampered")], [("unknown_revision", "unknown")]])
def test_migration_refuses_unknown_or_modified_prefix(monkeypatch, rows):
    conn = Connection(rows)
    monkeypatch.setattr(module.psycopg, "connect", lambda *a, **k: conn)
    with pytest.raises(RuntimeError, match="schema_revision_mismatch"):
        module.migrate("synthetic-dsn")
    assert not any("CREATE TABLE intake_submissions" in query for query, _ in conn.statements)
