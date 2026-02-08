import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from emerald.iam.domain.models.access_token_claims import AccessTokenClaims
from emerald.iam.domain.models.system_role import SystemRole
from emerald.shared_kernel.domain.exceptions import InvalidValueError


def _make_claims(**overrides: Any) -> AccessTokenClaims:
    """Build valid AccessTokenClaims with sensible defaults."""
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "sub": uuid.uuid4(),
        "email": "user@example.com",
        "system_role": SystemRole.USER,
        "iat": now,
        "exp": now + timedelta(minutes=15),
        "jti": uuid.uuid4(),
    }
    defaults.update(overrides)
    return AccessTokenClaims(**defaults)


class TestAccessTokenClaimsConstruction:
    def test_valid_construction(self):
        now = datetime.now(UTC)
        sub = uuid.uuid4()
        jti = uuid.uuid4()
        claims = AccessTokenClaims(
            sub=sub,
            email="user@example.com",
            system_role=SystemRole.USER,
            iat=now,
            exp=now + timedelta(minutes=15),
            jti=jti,
        )
        assert claims.sub == sub
        assert claims.email == "user@example.com"
        assert claims.system_role == SystemRole.USER
        assert claims.iat == now
        assert claims.exp == now + timedelta(minutes=15)
        assert claims.jti == jti

    def test_exp_equal_to_iat_raises(self):
        now = datetime.now(UTC)
        with pytest.raises(InvalidValueError):
            AccessTokenClaims(
                sub=uuid.uuid4(),
                email="user@example.com",
                system_role=SystemRole.USER,
                iat=now,
                exp=now,
                jti=uuid.uuid4(),
            )

    def test_exp_before_iat_raises(self):
        now = datetime.now(UTC)
        with pytest.raises(InvalidValueError):
            AccessTokenClaims(
                sub=uuid.uuid4(),
                email="user@example.com",
                system_role=SystemRole.USER,
                iat=now,
                exp=now - timedelta(minutes=5),
                jti=uuid.uuid4(),
            )

    def test_naive_iat_raises(self):
        now_utc = datetime.now(UTC)
        naive_iat = datetime(2025, 1, 1, 12, 0, 0)
        with pytest.raises(InvalidValueError):
            AccessTokenClaims(
                sub=uuid.uuid4(),
                email="user@example.com",
                system_role=SystemRole.USER,
                iat=naive_iat,
                exp=now_utc + timedelta(minutes=15),
                jti=uuid.uuid4(),
            )

    def test_naive_exp_raises(self):
        now_utc = datetime.now(UTC)
        naive_exp = datetime(2099, 1, 1, 12, 0, 0)
        with pytest.raises(InvalidValueError):
            AccessTokenClaims(
                sub=uuid.uuid4(),
                email="user@example.com",
                system_role=SystemRole.USER,
                iat=now_utc,
                exp=naive_exp,
                jti=uuid.uuid4(),
            )

    def test_non_utc_iat_raises(self):
        eastern = timezone(timedelta(hours=-5))
        non_utc_iat = datetime.now(eastern)
        utc_exp = datetime.now(UTC) + timedelta(minutes=15)
        with pytest.raises(InvalidValueError):
            AccessTokenClaims(
                sub=uuid.uuid4(),
                email="user@example.com",
                system_role=SystemRole.USER,
                iat=non_utc_iat,
                exp=utc_exp,
                jti=uuid.uuid4(),
            )

    def test_non_utc_exp_raises(self):
        eastern = timezone(timedelta(hours=-5))
        utc_iat = datetime.now(UTC)
        non_utc_exp = datetime.now(eastern) + timedelta(minutes=15)
        with pytest.raises(InvalidValueError):
            AccessTokenClaims(
                sub=uuid.uuid4(),
                email="user@example.com",
                system_role=SystemRole.USER,
                iat=utc_iat,
                exp=non_utc_exp,
                jti=uuid.uuid4(),
            )


class TestAccessTokenClaimsImmutability:
    def test_frozen(self):
        claims = _make_claims()
        with pytest.raises(AttributeError):
            claims.sub = uuid.uuid4()  # type: ignore[misc]
