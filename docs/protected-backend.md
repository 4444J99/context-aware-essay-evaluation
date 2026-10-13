# Protected edu backend

Owner: P1 / issue #2. T1.1 implementation; T1.2 identity-token verification foundation.

The protected FastAPI application is separate from the synthetic workbench. PostgreSQL stores
instructor provisioning, terms, courses, sections, pseudonymous enrollment allocations and scoped
predecessor references. There are no student names, essay bodies, grades or model routes in this
schema. T1.2's durable encrypted vault and actual identity-provider login integration remain required
before historical classroom data can be ingested. All development records must be invented.

## Run

Install locked dependencies with `uv sync --locked --extra test`. Configure operator-owned
values outside Git and without printing connection strings or identity tokens:

- EDU_MIGRATION_DATABASE_URL: PostgreSQL administrator connection for schema operations only.
- EDU_DATABASE_URL: separate runtime role with the permissions below.
- EDU_OIDC_ISSUER: exact HTTPS issuer.
- EDU_OIDC_AUDIENCE: dedicated API audience, distinct from a browser client ID.
- EDU_OIDC_JWKS_URL: pinned HTTPS signing-key URL from the chosen issuer's metadata.

Run `uv run essay-evaluation migrate` as the migration identity. Run
`uv run essay-evaluation serve-backend --port 8790` as the runtime identity. The listener is
loopback-only; hosted TLS/ingress configuration and provider selection belong to T1.3.
Remote PostgreSQL connections must use certificate verification (`sslmode=verify-full`) and
operator-managed trust roots. No credentials or identity provider are provisioned by this code.

Use a dedicated runtime role with NOSUPERUSER, NOBYPASSRLS, NOCREATEDB and NOCREATEROLE.
It must own no application tables and inherit no table-owning role. Grant only:

```sql
GRANT CONNECT ON DATABASE edu TO edu_api;
GRANT USAGE ON SCHEMA public TO edu_api;
GRANT SELECT ON instructors, schema_revisions TO edu_api;
GRANT SELECT, INSERT ON terms, courses, sections, enrollments, external_references TO edu_api;
```

An administrator provisions an instructor UUID with the exact issuer/subject tuple in
`instructors`; the runtime role cannot insert or modify that table. Set active=false to revoke
future API requests. Provisioning is a deliberate operation; a valid token does not automatically
create an instructor. The startup guard rejects elevated/table-owning roles and mismatched schema
revisions. Schema migration hashes prevent silently changing an already applied revision.

## Identity and scope contract

Every data endpoint requires a Bearer token verified using RS256, the pinned issuer/JWKS URL,
the configured API audience, required exp/iat/sub claims and MFA authentication methods.
Accepted MFA indicators are amr containing `mfa`, or both `pwd` and `otp`. Missing or unsupported
indicators hold access; issuer-specific policy mapping requires an explicit reviewed adapter.
No algorithm, issuer or key URL is taken from unverified token claims. JWKS requests have a
five-second timeout and a bounded cache lifetime. There is no anonymous authentication fallback.
This validates API tokens; it does not implement browser OIDC authorization-code/PKCE login.

Each request resolves the active provisioned instructor, sets transaction-local PostgreSQL
scope, runs parameterized statements and commits before sending a successful response. No
caller-supplied instructor ID or role is accepted. API parent checks plus composite foreign keys
prevent cross-instructor and cross-course writes. Forced row-level security restricts all six
application tables, including queries that omit API filters. Transaction scope is not reused.
Known foreign IDs produce the same 404 as absent records. Errors omit database internals and
validation input values. Responses have no-store and nosniff headers; CORS is not enabled.

Runtime credentials must remain confined to the trusted API. RLS uses server-set scope and is
additional protection against application mistakes; possession of the runtime database credential
is not safe access for a browser or other untrusted client.

## API

- GET /health: mode and capability boundary.
- GET /v1/session: verified instructor UUID.
- POST /v1/terms and GET /v1/terms: term metadata and dates.
- POST /v1/courses and GET /v1/courses: scoped course metadata.
- GET /v1/courses/{id}: scoped detail.
- POST/GET /v1/courses/{id}/sections: section metadata.
- POST/GET /v1/courses/{id}/sections/{section}/enrollments: allocate/list opaque references.
- POST/GET /v1/courses/{id}/references: map teacher_dashboard/aetheria/edu opaque external IDs
  to a course, section or enrollment within that course. Database trigger checks target scope.

Lists return items and next_cursor. Pass that cursor as `after` for the next page. A page holds
at most 100 entries; callers must consume all pages before claiming complete coverage. Invalid
metadata is rejected; conflicting references return 409. Assignment/submission mappings await
those entities' schema migration and cannot currently be submitted as reference kinds.

## Verification and dashboard sequence

`uv run --locked --extra test pytest` runs token checks, existing foundation checks and real
PostgreSQL integration tests. Tests start an isolated native cluster with a private Unix socket,
or use a disposable CI cluster through EDU_TEST_ADMIN_DSN. The suite creates uniquely named
synthetic databases/roles and removes only those resources. Never point it at production.
A missing PostgreSQL environment fails; SQLite is not used to imitate RLS evidence.

Integration acceptance covers migrate/reapply/empty rollback, refusal to rollback populated
schemas, unsafe runtime roles, provision/revocation, foreign-ID reads and writes, composite
scope constraints, external-target checks, direct-query RLS and no-scope connections.
CI supplies PostgreSQL 17. Local resource admission remains required before starting a cluster.

Next: finish T1.2 durable vault/key separation, issuer-backed login and restore checks, then
T1.3 staging. Adapt legacy React views through these authenticated endpoints in T2.3.
Remove Firebase/Spark persistence and model calls from extracted views. Preserve the original
MIT notice when copying substantial Aetheria code. The agreed Next.js workspace remains the
web target; protected backend qualification precedes dashboard integration.

Implementation references: [PyJWT verification](https://pyjwt.readthedocs.io/en/stable/usage.html)
and [psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

## Protected fixture intake upgrade

The backend now requires migration 002 and eight forced-RLS tables. See
[protected intake configuration and grants](protected-intake.md) for the disabled-by-default
synthetic extraction/privacy workflow. Original migration 001 remains unchanged.
