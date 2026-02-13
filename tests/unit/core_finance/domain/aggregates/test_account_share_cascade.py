import uuid
from decimal import Decimal

from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)


def _make_account(owner_id: uuid.UUID | None = None) -> Account:
    uid = owner_id or uuid.uuid4()
    owner = UserReference(user_id=uid, display_name="Owner")
    account = Account.create(
        owner=owner,
        account_name=AccountName("Test"),
        currency=Currency.USD,
        opening_balance=Money(Decimal("0"), Currency.USD),
        account_type_id=uuid.uuid4(),
        financial_institution_id=uuid.uuid4(),
    )
    account.collect_events()
    return account


def _default_retention() -> RetentionPeriod:
    return RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)


class TestSoftDeleteCascade:
    def test_revokes_non_owner_shares(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        viewer = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.share_with(viewer, PermissionLevel.VIEWER, owner_id)
        account.soft_delete(owner_id, _default_retention())
        # Owner share retained, others revoked
        assert account.active_share_count == 1
        assert account.is_owner(owner_id)

    def test_cascade_sets_revoked_by(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.soft_delete(owner_id, _default_retention())
        # Find the revoked share
        all_shares = [s for s in account._shares if s.user_id == editor]
        assert len(all_shares) == 1
        assert all_shares[0].revoked_by == owner_id

    def test_owner_share_retained(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        account.share_with(uuid.uuid4(), PermissionLevel.EDITOR, owner_id)
        account.soft_delete(owner_id, _default_retention())
        owner_share = account.get_owner()
        assert owner_share.is_active()
        assert owner_share.user_id == owner_id

    def test_no_non_owner_shares_no_error(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        account.soft_delete(owner_id, _default_retention())
        assert account.is_deleted()
        assert account.active_share_count == 1


class TestRecoverDoesNotRestoreShares:
    def test_shares_remain_revoked_after_recovery(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        viewer = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.share_with(viewer, PermissionLevel.VIEWER, owner_id)
        account.soft_delete(owner_id, _default_retention())
        account.collect_events()
        account.recover()
        assert account.is_active()
        assert account.active_share_count == 1  # only owner
        assert account.is_owner(owner_id)
        assert account.get_share_for_user(editor) is None
        assert account.get_share_for_user(viewer) is None

    def test_account_active_after_recovery(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        account.share_with(uuid.uuid4(), PermissionLevel.EDITOR, owner_id)
        account.soft_delete(owner_id, _default_retention())
        account.collect_events()
        account.recover()
        assert not account.is_deleted()

    def test_large_cascade_all_revoked(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        for _ in range(19):
            account.share_with(uuid.uuid4(), PermissionLevel.VIEWER, owner_id)
        assert account.active_share_count == 20
        account.soft_delete(owner_id, _default_retention())
        assert account.active_share_count == 1
        account.collect_events()
        account.recover()
        assert account.active_share_count == 1
