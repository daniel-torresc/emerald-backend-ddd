from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt as pyjwt
import pytest

from emerald.iam.adapters.outbound.auth.jwt_token_service import JwtTokenService
from emerald.iam.domain.exceptions import InvalidTokenError, TokenExpiredError
from emerald.iam.domain.models.value_objects.access_token_claims import AccessTokenClaims
from emerald.iam.domain.models.value_objects.system_role import SystemRole
from emerald.shared_kernel.infrastructure.config.settings import JwtSettings


@pytest.fixture
def jwt_settings() -> JwtSettings:
    return JwtSettings(
        secret_key="test-secret-key-that-is-long-enough",
        algorithm="HS256",
        access_token_ttl_minutes=15,
        refresh_token_ttl_days=30,
        issuer="test-issuer",
    )


@pytest.fixture
def service(jwt_settings: JwtSettings) -> JwtTokenService:
    return JwtTokenService(jwt_settings)


@pytest.fixture
def sample_claims() -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        sub=uuid4(),
        email="user@example.com",
        username="testuser",
        system_role=SystemRole.USER,
        iat=now,
        exp=now + timedelta(minutes=15),
        jti=uuid4(),
    )


class TestJwtTokenService:
    async def test_sign_and_verify_round_trip(
        self, service: JwtTokenService, sample_claims: AccessTokenClaims
    ) -> None:
        token = await service.sign_access_token(sample_claims)
        recovered = await service.verify_access_token(token)

        assert recovered.sub == sample_claims.sub
        assert recovered.email == sample_claims.email
        assert recovered.username == sample_claims.username
        assert recovered.system_role == sample_claims.system_role
        assert recovered.jti == sample_claims.jti
        # Timestamps may lose sub-second precision through JWT encoding
        assert abs((recovered.iat - sample_claims.iat).total_seconds()) < 1
        assert abs((recovered.exp - sample_claims.exp).total_seconds()) < 1

    async def test_payload_contains_all_claims(
        self, service: JwtTokenService, sample_claims: AccessTokenClaims
    ) -> None:
        token = await service.sign_access_token(sample_claims)
        payload = pyjwt.decode(token, options={"verify_signature": False})

        assert payload["sub"] == str(sample_claims.sub)
        assert payload["email"] == sample_claims.email
        assert payload["username"] == sample_claims.username
        assert payload["system_role"] == sample_claims.system_role.value
        assert payload["iss"] == "test-issuer"
        assert payload["jti"] == str(sample_claims.jti)
        assert "iat" in payload
        assert "exp" in payload

    async def test_verify_expired_token_raises_token_expired(
        self, service: JwtTokenService
    ) -> None:
        now = datetime.now(UTC)
        claims = AccessTokenClaims(
            sub=uuid4(),
            email="user@example.com",
            system_role=SystemRole.USER,
            iat=now - timedelta(hours=2),
            exp=now - timedelta(hours=1),
            jti=uuid4(),
        )
        token = await service.sign_access_token(claims)

        with pytest.raises(TokenExpiredError):
            await service.verify_access_token(token)

    async def test_verify_invalid_signature_raises_invalid_token(
        self, sample_claims: AccessTokenClaims
    ) -> None:
        wrong_settings = JwtSettings(
            secret_key="different-secret-key-for-testing-xxxxx",
            algorithm="HS256",
            issuer="test-issuer",
        )
        wrong_service = JwtTokenService(wrong_settings)
        token = await wrong_service.sign_access_token(sample_claims)

        correct_settings = JwtSettings(
            secret_key="correct-secret-key-for-testing-xxxxxxx",
            algorithm="HS256",
            issuer="test-issuer",
        )
        correct_service = JwtTokenService(correct_settings)

        with pytest.raises(InvalidTokenError):
            await correct_service.verify_access_token(token)

    async def test_verify_wrong_issuer_raises_invalid_token(
        self, sample_claims: AccessTokenClaims
    ) -> None:
        settings_a = JwtSettings(
            secret_key="shared-secret-key-for-testing-xxxxxxxx",
            algorithm="HS256",
            issuer="issuer-a",
        )
        settings_b = JwtSettings(
            secret_key="shared-secret-key-for-testing-xxxxxxxx",
            algorithm="HS256",
            issuer="issuer-b",
        )
        service_a = JwtTokenService(settings_a)
        service_b = JwtTokenService(settings_b)

        token = await service_a.sign_access_token(sample_claims)

        with pytest.raises(InvalidTokenError):
            await service_b.verify_access_token(token)

    async def test_verify_malformed_token_raises_invalid_token(
        self, service: JwtTokenService
    ) -> None:
        with pytest.raises(InvalidTokenError):
            await service.verify_access_token("not-a-valid-jwt-token")

    async def test_verify_missing_claims_raises_invalid_token(
        self, jwt_settings: JwtSettings
    ) -> None:
        # Manually create a JWT missing required fields
        payload = {"sub": str(uuid4()), "iss": jwt_settings.issuer}
        token = pyjwt.encode(payload, jwt_settings.secret_key, algorithm=jwt_settings.algorithm)

        service = JwtTokenService(jwt_settings)
        with pytest.raises(InvalidTokenError):
            await service.verify_access_token(token)

    async def test_generate_refresh_token_returns_tuple(self, service: JwtTokenService) -> None:
        result = await service.generate_refresh_token()
        assert isinstance(result, tuple)
        assert len(result) == 2
        raw, hashed = result
        assert isinstance(raw, str)
        assert isinstance(hashed, str)
        assert len(hashed) == 64  # SHA-256 hex digest length

    async def test_generate_refresh_token_unique(self, service: JwtTokenService) -> None:
        result1 = await service.generate_refresh_token()
        result2 = await service.generate_refresh_token()
        assert result1[0] != result2[0]

    async def test_hash_token_deterministic(self, service: JwtTokenService) -> None:
        hash1 = await service.hash_token("same-input")
        hash2 = await service.hash_token("same-input")
        assert hash1 == hash2

    async def test_hash_token_matches_generate(self, service: JwtTokenService) -> None:
        raw, expected_hash = await service.generate_refresh_token()
        actual_hash = await service.hash_token(raw)
        assert actual_hash == expected_hash

    async def test_username_none_handled(self, service: JwtTokenService) -> None:
        now = datetime.now(UTC)
        claims = AccessTokenClaims(
            sub=uuid4(),
            email="user@example.com",
            username=None,
            system_role=SystemRole.USER,
            iat=now,
            exp=now + timedelta(minutes=15),
            jti=uuid4(),
        )
        token = await service.sign_access_token(claims)
        recovered = await service.verify_access_token(token)
        assert recovered.username is None
