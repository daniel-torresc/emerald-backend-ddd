import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from emerald.core_finance.domain.exceptions.sharing_exceptions import ShareAlreadyRevokedError
from emerald.core_finance.domain.models.entities.account_share import AccountShare
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel


def _make_share(**overrides: Any) -> AccountShare:
    defaults: dict[str, Any] = {
        "account_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "permission_level": PermissionLevel.EDITOR,
        "granted_by": uuid.uuid4(),
    }
    defaults.update(overrides)
    return AccountShare(**defaults)


class TestAccountShareConstruction:
    def test_creates_with_required_fields(self) -> None:
        share = _make_share()
        assert isinstance(share.id, uuid.UUID)
        assert share.permission_level == PermissionLevel.EDITOR

    def test_granted_at_defaults_to_now(self) -> None:
        before = datetime.now(UTC)
        share = _make_share()
        assert share.granted_at >= before

    def test_updated_at_defaults_to_granted_at(self) -> None:
        share = _make_share()
        assert share.updated_at == share.granted_at

    def test_revoked_at_defaults_to_none(self) -> None:
        share = _make_share()
        assert share.revoked_at is None

    def test_revoked_by_defaults_to_none(self) -> None:
        share = _make_share()
        assert share.revoked_by is None

    def test_explicit_id(self) -> None:
        sid = uuid.uuid4()
        share = _make_share(id=sid)
        assert share.id == sid


class TestIsActive:
    def test_active_when_not_revoked(self) -> None:
        share = _make_share()
        assert share.is_active() is True

    def test_not_active_when_revoked(self) -> None:
        share = _make_share()
        share.revoke(uuid.uuid4())
        assert share.is_active() is False


class TestIsRevoked:
    def test_not_revoked_initially(self) -> None:
        share = _make_share()
        assert share.is_revoked() is False

    def test_revoked_after_revocation(self) -> None:
        share = _make_share()
        share.revoke(uuid.uuid4())
        assert share.is_revoked() is True


class TestRevoke:
    def test_sets_revoked_at(self) -> None:
        share = _make_share()
        before = datetime.now(UTC)
        share.revoke(uuid.uuid4())
        assert share.revoked_at is not None
        assert share.revoked_at >= before

    def test_sets_revoked_by(self) -> None:
        share = _make_share()
        actor = uuid.uuid4()
        share.revoke(actor)
        assert share.revoked_by == actor

    def test_double_revoke_raises(self) -> None:
        share = _make_share()
        share.revoke(uuid.uuid4())
        with pytest.raises(ShareAlreadyRevokedError):
            share.revoke(uuid.uuid4())


class TestUpdatePermission:
    def test_changes_permission_level(self) -> None:
        share = _make_share(permission_level=PermissionLevel.VIEWER)
        share.update_permission(PermissionLevel.EDITOR)
        assert share.permission_level == PermissionLevel.EDITOR

    def test_refreshes_updated_at(self) -> None:
        share = _make_share()
        original_updated_at = share.updated_at
        share.update_permission(PermissionLevel.VIEWER)
        assert share.updated_at >= original_updated_at


class TestIdentityEquality:
    def test_same_id_equal(self) -> None:
        sid = uuid.uuid4()
        share1 = _make_share(id=sid)
        share2 = _make_share(id=sid)
        assert share1 == share2

    def test_different_id_not_equal(self) -> None:
        share1 = _make_share()
        share2 = _make_share()
        assert share1 != share2
