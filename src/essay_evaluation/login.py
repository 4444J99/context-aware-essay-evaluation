"""OIDC code/PKCE login and opaque browser sessions; tokens stay server-side."""
import base64
from dataclasses import dataclass, field
from hashlib import sha256
import secrets
import time
from urllib.parse import urlencode, urlsplit

from cryptography.exceptions import InvalidTag
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx
import sqlite3

from .auth import AuthenticationError, TokenVerifier
from .sessions import SessionStore

ATTEMPT_COOKIE = "__Host-edu-login"
SESSION_COOKIE = "__Host-edu-session"


def digest(value: str) -> str:
    return base64.urlsafe_b64encode(sha256(value.encode()).digest()).rstrip(b"=").decode()


@dataclass(frozen=True)
class LoginConfig:
    origin: str
    authorization_url: str
    token_url: str
    client_id: str
    client_secret: str | None = field(default=None, repr=False)

    def __post_init__(self):
        for value in (self.origin, self.authorization_url, self.token_url):
            url = urlsplit(value)
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError("pinned_https_login_endpoints_required")
        if urlsplit(self.origin).path or not self.client_id:
            raise ValueError("login_origin_or_client_invalid")

    @property
    def callback(self):
        return self.origin + "/auth/callback"


class BrowserLogin:
    def __init__(self, config: LoginConfig, store: SessionStore, api_verifier: TokenVerifier,
                 id_verifier: TokenVerifier, database, transport=None, clock=time.time):
        if config.client_id != id_verifier.audience or api_verifier.audience == config.client_id or api_verifier.issuer != id_verifier.issuer:
            raise ValueError("distinct_browser_and_api_audiences_required")
        self.config, self.store = config, store
        self.api_verifier, self.id_verifier = api_verifier, id_verifier
        self.database, self.transport, self.clock = database, transport, clock

    def start(self):
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        self.store.create("attempt", state, {"nonce": nonce, "verifier": verifier}, int(self.clock()) + 300)
        query = {"response_type": "code", "client_id": self.config.client_id, "scope": "openid",
                 "redirect_uri": self.config.callback, "state": state, "nonce": nonce,
                 "code_challenge": digest(verifier), "code_challenge_method": "S256"}
        response = RedirectResponse(self.config.authorization_url + "?" + urlencode(query), status_code=302)
        response.set_cookie(ATTEMPT_COOKIE, state, max_age=300, secure=True, httponly=True, samesite="lax", path="/")
        return response

    def finish(self, code, state, cookie):
        if not cookie or len(state) > 256 or len(cookie) > 256 or not secrets.compare_digest(state.encode(), cookie.encode()):
            raise HTTPException(400, "login_state_invalid")
        attempt = self.store.get("attempt", state, consume=True)
        if attempt is None or not code:
            raise HTTPException(400, "login_attempt_expired_or_used")
        body = {"grant_type": "authorization_code", "code": code, "redirect_uri": self.config.callback,
                "client_id": self.config.client_id, "code_verifier": attempt["verifier"]}
        auth = (self.config.client_id, self.config.client_secret) if self.config.client_secret else None
        try:
            with httpx.Client(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, transport=self.transport) as client:
                with client.stream("POST", self.config.token_url, data=body, auth=auth) as response:
                    if response.status_code != 200:
                        raise HTTPException(400, "login_exchange_failed")
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 65536:
                            raise HTTPException(400, "login_response_invalid")
                    import json
                    result = json.loads(raw)
            access = result["access_token"]
            identity_token = result["id_token"]
            if result.get("token_type", "").lower() != "bearer" or not isinstance(access, str) or not isinstance(identity_token, str):
                raise AuthenticationError("login_token_type_invalid")
            id_claims = self.id_verifier.verify_claims(identity_token)
            api_claims = self.api_verifier.verify_claims(access)
            if id_claims.get("nonce") != attempt["nonce"] or id_claims["sub"] != api_claims["sub"]:
                raise AuthenticationError("login_token_binding_invalid")
            audiences = id_claims["aud"]
            if (isinstance(audiences, list) and len(audiences) > 1 and id_claims.get("azp") != self.config.client_id) or ("azp" in id_claims and id_claims["azp"] != self.config.client_id):
                raise AuthenticationError("login_authorized_party_invalid")
            if "at_hash" in id_claims:
                expected = base64.urlsafe_b64encode(sha256(access.encode()).digest()[:16]).rstrip(b"=").decode()
                if id_claims["at_hash"] != expected:
                    raise AuthenticationError("login_access_binding_invalid")
            expires = min(int(id_claims["exp"]), int(api_claims["exp"]), int(self.clock()) + 900)
            with self.database.scoped(self.api_verifier.issuer, api_claims["sub"]):
                pass
            session_id = secrets.token_urlsafe(32)
            self.store.create("browser", session_id, {"access_token": access, "subject": api_claims["sub"],
                                                     "csrf": secrets.token_urlsafe(32)}, expires)
            return session_id, expires
        except PermissionError:
            raise HTTPException(403, "instructor_not_provisioned") from None
        except httpx.HTTPError:
            raise HTTPException(503, "identity_provider_unavailable") from None
        except (AuthenticationError, ValueError, TypeError, KeyError, AttributeError):
            raise HTTPException(400, "login_response_invalid") from None

    def identity(self, request: Request):
        opaque = request.cookies.get(SESSION_COOKIE, "")
        try:
            session = self.store.get("browser", opaque)
            if session is None:
                raise HTTPException(401, "browser_login_required")
            identity = self.api_verifier.verify(session["access_token"])
            if identity.subject != session["subject"]:
                raise AuthenticationError("session_subject_mismatch")
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                csrf = request.headers.get("x-csrf-token", "")
                if request.headers.get("origin") != self.config.origin or len(csrf) > 256 or not secrets.compare_digest(csrf.encode(), session["csrf"].encode()):
                    raise HTTPException(403, "csrf_validation_failed")
            return identity, session["csrf"]
        except AuthenticationError:
            raise HTTPException(401, "browser_session_invalid") from None
        except (OSError, ValueError, InvalidTag, sqlite3.Error, KeyError, TypeError):
            raise HTTPException(503, "session_storage_unavailable") from None


def install_login_routes(app: FastAPI, login: BrowserLogin):
    @app.exception_handler(InvalidTag)
    @app.exception_handler(sqlite3.Error)
    @app.exception_handler(OSError)
    async def unavailable_storage(request: Request, error: Exception):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "session_storage_unavailable"}, status_code=503)

    @app.get("/", response_class=HTMLResponse)
    def landing():
        return '<h1>edu</h1><p>Protected instructor service.</p><a href="/auth/login">Sign in</a>'

    @app.get("/auth/login")
    def start():
        return login.start()

    @app.get("/auth/callback")
    def callback(request: Request, state: str = Query(default="", max_length=256), code: str = Query(default="", max_length=4096)):
        session_id, expires = login.finish(code, state, request.cookies.get(ATTEMPT_COOKIE, ""))
        login.store.revoke("browser", request.cookies.get(SESSION_COOKIE, ""))
        response = RedirectResponse("/", status_code=303)
        response.set_cookie(SESSION_COOKIE, session_id, max_age=max(0, expires-int(login.clock())), secure=True, httponly=True, samesite="lax", path="/")
        response.delete_cookie(ATTEMPT_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
        return response

    @app.get("/auth/session")
    def session(request: Request):
        identity, csrf = login.identity(request)
        try:
            with login.database.scoped(identity.issuer, identity.subject) as (_, owner):
                return {"product": "edu", "instructor_id": str(owner), "csrf_token": csrf}
        except PermissionError:
            raise HTTPException(403, "instructor_not_provisioned") from None

    @app.post("/auth/logout", status_code=303)
    def logout(request: Request):
        login.identity(request)
        login.store.revoke("browser", request.cookies.get(SESSION_COOKIE, ""))
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
        return response
