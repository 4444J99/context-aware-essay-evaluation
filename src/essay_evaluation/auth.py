"""Pinned-issuer JWT verification; identity does not imply instructor provisioning."""
from dataclasses import dataclass
from urllib.parse import urlsplit

import jwt
from jwt import PyJWKClient


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str


class AuthenticationError(ValueError):
    pass


class TokenVerifier:
    def __init__(self, issuer: str, audience: str, jwks_url: str):
        for url in (issuer, jwks_url):
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
                raise ValueError("https_identity_configuration_required")
        if not audience:
            raise ValueError("audience_required")
        self.issuer = issuer
        self.audience = audience
        # Only this operator-configured URL is fetched; token jku/x5u never select a URL.
        self.jwks = PyJWKClient(jwks_url, timeout=5, lifespan=300)

    def verify_claims(self, token: str) -> dict:  # allow-secret: token parameter only; no credential literal
        if len(token) > 16384:
            raise AuthenticationError("invalid_identity_token")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise AuthenticationError("invalid_identity_token")
            key = self.jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"], issuer=self.issuer,
                audience=self.audience, options={"require": ["exp", "iat", "iss", "aud", "sub", "amr"]},
            )
            amr = claims["amr"]
            if not isinstance(amr, list) or not all(isinstance(v, str) for v in amr):
                raise AuthenticationError("mfa_required")
            if "mfa" not in amr and not {"pwd", "otp"}.issubset(amr):
                raise AuthenticationError("mfa_required")
            if not isinstance(claims["sub"], str) or not claims["sub"] or len(claims["sub"]) > 512:
                raise AuthenticationError("invalid_identity_token")
            return claims
        except AuthenticationError:
            raise
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise AuthenticationError("invalid_identity_token") from exc

    def verify(self, token: str) -> Identity:  # allow-secret: token parameter only; no credential literal
        claims = self.verify_claims(token)
        return Identity(self.issuer, claims["sub"])
