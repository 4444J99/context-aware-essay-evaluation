# Durable vault and browser login

T1.2 is in progress under edu. These components use synthetic data only. They do not open student ingestion or qualify a hosted pilot.

## Vault boundary

`DurableVault` stores immutable authenticated ciphertext with a fresh data key per object. Wrapping keys are supplied externally, versioned and bound to one of identity, content or session. Object authentication binds domain, scope and object ID. Atomic publication, private owned directories/files, bounded reads and symlink rejection protect the filesystem adapter. Rewrapping preserves payload ciphertext and object IDs.

Use separate processes and credentials for content and identity domains. A content worker must never receive identity keys. The current adapter demonstrates cryptographic separation; hosted KMS IAM separation and object storage remain T1.2 acceptance work. The configured root and its ancestors must be trusted OS-owned private storage. Same-user OS compromise is outside this adapter's boundary.

Restore tests copy ciphertext and independently supply the original wrapping keys. Keys are never included in the vault. Keep old versions available until retained backups expire; new-key-only operation cannot restore old-key backups. This is a component restore test, not a qualified backup service. Crash orphan reconciliation, authenticated inventories and physical retention/deletion remain T6.2 work.

## Browser flow

Enable explicitly with `EDU_LOGIN_ENABLED=true`. Configure the existing protected database and API issuer/audience/JWKS settings plus:

- `EDU_APP_ORIGIN`: exact HTTPS origin, without a trailing slash or path.
- `EDU_OIDC_AUTHORIZATION_URL` and `EDU_OIDC_TOKEN_URL`: pinned HTTPS endpoints without query or fragment.
- `EDU_OIDC_CLIENT_ID`: browser audience, distinct from API audience; optional `EDU_OIDC_CLIENT_SECRET` supplied through the credential system.
- `EDU_SESSION_ROOT`: owned private directory on persistent storage.
- `EDU_SESSION_KEYS_JSON`: credential-injected mapping of key version to base64-encoded 32-byte session wrapping key; `EDU_SESSION_KEY_VERSION` selects the current version. Do not put values in source, shell history or receipts.

Register the exact origin plus `/auth/callback` with the issuer. Its authorization-code flow must return signed RS256 ID and API access tokens with supported MFA evidence. No identity is auto-provisioned. Both tokens must bind the same subject, issuer and proper audiences; nonce, authorized party and supplied access-token hash are checked. Provider-specific API audience configuration and a real institution login still require qualification.

`/auth/login` creates a five-minute state/nonce/PKCE attempt. Callback consumes it once, including uncertain exchange failures. A browser session lasts at most fifteen minutes and never outlives either token. Secure, HttpOnly, SameSite cookies carry opaque IDs. Access tokens and CSRF material remain in the encrypted server vault. Writes require exact Origin and CSRF header; token verification and active instructor scope are rechecked. `/auth/session` returns only instructor ID and CSRF material. `/auth/logout` revokes the local session; it does not revoke an issuer session. There is no refresh-token flow.

SQLite is only the opaque session index; academic records still require PostgreSQL. Expired/revoked session ciphertext is not yet physically purged. Index capacity is bounded, and operational rate limiting is T1.3 work. The minimal landing page is a service entry point; reusable instructor dashboard integration remains T2.3.

## Evidence and remaining gates

Tests use generated signing keys, mocked issuer transport and a fake provisioned instructor boundary. They exercise replay, expiry, CSRF, persistence, tamper rejection, key rotation and restore. They do not establish real PostgreSQL isolation, live provider compatibility or hosted KMS acceptance. Existing database and runner admission blockers remain owned by P1 issue #2; no repeated unchanged bootstrap was attempted.

References: [OIDC Core](https://openid.net/specs/openid-connect-core-1_0.html), [PKCE](https://www.rfc-editor.org/rfc/rfc7636), [AES-GCM API](https://cryptography.io/en/latest/hazmat/primitives/aead/).
