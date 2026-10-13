from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest

from essay_evaluation.auth import TokenVerifier
from essay_evaluation.backend import create_backend
from essay_evaluation.durable_vault import DomainKeyRing, DurableVault
from essay_evaluation.login import BrowserLogin, LoginConfig, ATTEMPT_COOKIE, SESSION_COOKIE, digest
from essay_evaluation.sessions import SessionStore

ORIGIN = "https://edu.example.test"
ISSUER = "https://issuer.example.test"


@pytest.fixture(scope="module")
def signer():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class ProvisionedDatabase:
    def __init__(self):
        self.owner = uuid4()
        self.allowed = True

    def verify(self):
        pass

    @contextmanager
    def scoped(self, issuer, subject):
        if not self.allowed or issuer != ISSUER or subject != "synthetic-teacher":
            raise PermissionError("instructor_not_provisioned")
        yield None, self.owner


@pytest.fixture
def environment(tmp_path, signer):
    db = ProvisionedDatabase()
    def verifier(audience):
        value = TokenVerifier(ISSUER, audience, ISSUER + "/jwks")
        value.jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=signer.public_key()))
        return value
    api, identity = verifier("edu-api"), verifier("edu-browser")
    keys = DomainKeyRing("session", "v1", {"v1": AESGCM.generate_key(bit_length=256)})
    vault = DurableVault(tmp_path / "vault", keys)
    store = SessionStore(tmp_path / "index", vault)
    expected = {}
    fault = {"value": None, "calls": 0}

    def exchange(request):
        fault["calls"] += 1
        data = parse_qs(request.content.decode())
        assert request.url == ISSUER + "/token"
        assert data["code"] == ["synthetic-code"]
        assert digest(data["code_verifier"][0]) == expected["code_challenge"]
        assert data["redirect_uri"] == [ORIGIN + "/auth/callback"]
        if fault["value"] == "timeout":
            raise httpx.ReadTimeout("synthetic timeout")
        now = datetime.now(timezone.utc)
        common = {"iss": ISSUER, "sub": "synthetic-teacher", "iat": now, "exp": now + timedelta(minutes=5), "amr": ["pwd", "otp"]}
        access_claims = {**common, "aud": "edu-api"}
        id_claims = {**common, "aud": "edu-browser", "nonce": expected["nonce"]}
        if fault["value"] == "nonce": id_claims["nonce"] = "wrong"
        if fault["value"] == "subject": access_claims["sub"] = "someone-else"
        if fault["value"] == "mfa": access_claims["amr"] = ["pwd"]
        if fault["value"] == "audience": id_claims["aud"] = "wrong-browser"
        if fault["value"] == "authorized_party": id_claims["azp"] = "wrong-browser"
        if fault["value"] == "access_hash": id_claims["at_hash"] = "wrong"
        if fault["value"] == "expired": access_claims["exp"] = 1
        result = {"access_token": jwt.encode(access_claims, signer, algorithm="RS256", headers={"kid": "synthetic"}),
                  "id_token": jwt.encode(id_claims, signer, algorithm="RS256", headers={"kid": "synthetic"}), "token_type": "Bearer"}
        if fault["value"] == "oversize": return httpx.Response(200, content=b"x" * 65537)
        return httpx.Response(200, json=result)

    config = LoginConfig(ORIGIN, ISSUER + "/authorize", ISSUER + "/token", "edu-browser")
    login = BrowserLogin(config, store, api, identity, db, transport=httpx.MockTransport(exchange))
    return SimpleNamespace(db=db, api=api, id=identity, config=config, store=store, login=login,
                           expected=expected, fault=fault, tmp_path=tmp_path, keys=keys)


def begin(client, environment):
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302
    params = {k: v[0] for k, v in parse_qs(urlsplit(response.headers["location"]).query).items()}
    environment.expected.update(params)
    assert params["code_challenge_method"] == "S256"
    assert "code_verifier" not in params and "secret" not in response.headers["location"]
    assert "Secure" in response.headers["set-cookie"] and "HttpOnly" in response.headers["set-cookie"]
    return params["state"]


def complete(client, state):
    return client.get("/auth/callback", params={"state": state, "code": "synthetic-code"}, follow_redirects=False)


def test_login_session_restart_csrf_logout_and_replay(environment):
    e = environment
    with TestClient(create_backend(e.db, e.api, e.login), base_url=ORIGIN) as client:
        state = begin(client, e)
        response = complete(client, state)
        assert response.status_code == 303, response.text
        assert response.headers["location"] == "/"
        assert client.cookies.get(SESSION_COOKIE)
        assert not client.cookies.get(ATTEMPT_COOKIE)
        assert "access_token" not in response.text
        session = client.get("/auth/session")
        assert session.status_code == 200 and session.headers["cache-control"] == "no-store"
        csrf = session.json()["csrf_token"]
        assert client.get("/v1/session").json()["instructor_id"] == str(e.db.owner)
        # Protected API POSTs using cookies require both Origin and the session CSRF token.
        assert client.post("/v1/terms", json={"label": "x", "starts_on": "2026-01-01", "ends_on": "2026-12-01"}).status_code == 403
        assert client.post("/auth/logout", headers={"origin": "https://evil.example.test", "x-csrf-token": csrf}, follow_redirects=False).status_code == 403
        # Restart the state/session index and vault; keys are supplied externally again.
        restored_store = SessionStore(e.tmp_path / "index", DurableVault(e.tmp_path / "vault", e.keys))
        restored_login = BrowserLogin(e.config, restored_store, e.api, e.id, e.db)
        with TestClient(create_backend(e.db, e.api, restored_login), base_url=ORIGIN, cookies=dict(client.cookies)) as restored:
            assert restored.get("/auth/session").status_code == 200
            assert restored.post("/auth/logout", headers={"origin": ORIGIN, "x-csrf-token": csrf}, follow_redirects=False).status_code == 303
        assert client.get("/auth/session").status_code == 401
        client.cookies.set(ATTEMPT_COOKIE, state)
        assert complete(client, state).status_code == 400
        assert e.fault["calls"] == 1


@pytest.mark.parametrize("fault", ["nonce", "subject", "mfa", "audience", "authorized_party", "access_hash", "expired", "oversize"])
def test_token_response_binding_rejections(environment, fault):
    e = environment
    e.fault["value"] = fault
    with TestClient(create_backend(e.db, e.api, e.login), base_url=ORIGIN) as client:
        state = begin(client, e)
        response = complete(client, state)
        assert response.status_code == 400
        assert not client.cookies.get(SESSION_COOKIE)
        assert complete(client, state).status_code == 400
        assert e.fault["calls"] == 1


def test_wrong_state_expiry_unprovisioned_and_exchange_timeout(environment):
    e = environment
    with TestClient(create_backend(e.db, e.api, e.login), base_url=ORIGIN) as client:
        state = begin(client, e)
        assert complete(client, "wrong-state").status_code == 400
        assert e.fault["calls"] == 0
        e.db.allowed = False
        assert complete(client, state).status_code == 403
        assert not client.cookies.get(SESSION_COOKIE)
        e.db.allowed = True
        state = begin(client, e)
        e.fault["value"] = "timeout"
        assert complete(client, state).status_code == 503
        e.fault["value"] = None
        assert complete(client, state).status_code == 400
        state = begin(client, e)
        e.store.clock = lambda: 4102444800
        assert complete(client, state).status_code == 400


def test_revoked_instructor_and_expired_sessions_fail(environment):
    e = environment
    with TestClient(create_backend(e.db, e.api, e.login), base_url=ORIGIN) as client:
        state = begin(client, e)
        assert complete(client, state).status_code == 303
        e.db.allowed = False
        assert client.get("/auth/session").status_code == 403
        assert client.get("/v1/session").status_code == 403
        e.db.allowed = True
        e.store.clock = lambda: 4102444800
        assert client.get("/auth/session").status_code == 401


def test_https_and_audience_configuration(environment):
    e = environment
    with pytest.raises(ValueError):
        LoginConfig("http://edu.example.test", ISSUER + "/authorize", ISSUER + "/token", "edu-browser")
    with pytest.raises(ValueError):
        BrowserLogin(e.config, e.store, e.api, e.api, e.db)
