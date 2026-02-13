import uuid
from decimal import Decimal
from typing import Any

import pytest

from emerald.core_finance.domain.events.sharing_events import (
    AccountOwnershipTransferred,
    AccountShared,
    AccountShareLeft,
    AccountShareRevoked,
    AccountShareUpdated,
)
from emerald.core_finance.domain.exceptions.sharing_exceptions import (
    AccountNotActiveError,
    AlreadyOwnerError,
    AlreadySharedError,
    CannotGrantOwnerError,
    CannotLeaveAsOwnerError,
    CannotModifyOwnerShareError,
    CannotRevokeOwnerError,
    CannotShareWithSelfError,
    InsufficientPermissionError,
    MaxSharesReachedError,
    ShareNotFoundError,
)
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


def _make_account(owner_id: uuid.UUID | None = None, **overrides: Any) -> Account:
    uid = owner_id or uuid.uuid4()
    owner = UserReference(user_id=uid, display_name="Owner")
    defaults: dict[str, Any] = {
        "account_name": AccountName("Test Account"),
        "currency": Currency.USD,
        "opening_balance": Money(Decimal("1000.00"), Currency.USD),
        "account_type_id": uuid.uuid4(),
        "financial_institution_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    account = Account.create(owner=owner, **defaults)
    account.collect_events()  # clear creation event
    return account


def _default_retention() -> RetentionPeriod:
    return RetentionPeriod(duration=30, unit=RetentionUnit.DAYS)


# -- share_with tests ---------------------------------------------------------


class TestShareWith:
    def test_share_as_viewer(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        share = account.share_with(target, PermissionLevel.VIEWER, owner_id)
        assert share.user_id == target
        assert share.permission_level == PermissionLevel.VIEWER
        assert share.granted_by == owner_id
        assert share.account_id == account.id

    def test_share_as_editor(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        share = account.share_with(target, PermissionLevel.EDITOR, owner_id)
        assert share.permission_level == PermissionLevel.EDITOR

    def test_active_share_count_increments(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        account.share_with(uuid.uuid4(), PermissionLevel.VIEWER, owner_id)
        assert account.active_share_count == 2  # owner + new share

    def test_emits_account_shared_event(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.EDITOR, owner_id)
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountShared)
        assert event.user_id == target
        assert event.permission_level == "EDITOR"
        assert event.granted_by == owner_id

    def test_cannot_grant_owner(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        with pytest.raises(CannotGrantOwnerError):
            account.share_with(uuid.uuid4(), PermissionLevel.OWNER, owner_id)

    def test_cannot_share_with_self(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        with pytest.raises(CannotShareWithSelfError):
            account.share_with(owner_id, PermissionLevel.VIEWER, owner_id)

    def test_cannot_share_if_already_shared(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.VIEWER, owner_id)
        with pytest.raises(AlreadySharedError):
            account.share_with(target, PermissionLevel.EDITOR, owner_id)

    def test_cannot_share_deleted_account(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        account.soft_delete(owner_id, _default_retention())
        account.collect_events()
        with pytest.raises(AccountNotActiveError):
            account.share_with(uuid.uuid4(), PermissionLevel.VIEWER, owner_id)

    def test_non_owner_cannot_share(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        with pytest.raises(InsufficientPermissionError):
            account.share_with(uuid.uuid4(), PermissionLevel.VIEWER, editor)

    def test_max_shares_reached(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        # Fill to max (owner counts as 1, so add 19 more)
        for _ in range(19):
            account.share_with(uuid.uuid4(), PermissionLevel.VIEWER, owner_id)
        assert account.active_share_count == 20
        with pytest.raises(MaxSharesReachedError):
            account.share_with(uuid.uuid4(), PermissionLevel.VIEWER, owner_id)

    def test_reshare_after_revoke_allowed(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.VIEWER, owner_id)
        account.revoke_share(target, owner_id)
        # Re-sharing is allowed
        share = account.share_with(target, PermissionLevel.EDITOR, owner_id)
        assert share.permission_level == PermissionLevel.EDITOR


# -- update_share_permission tests --------------------------------------------


class TestUpdateSharePermission:
    def test_viewer_to_editor(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.VIEWER, owner_id)
        account.collect_events()
        account.update_share_permission(target, PermissionLevel.EDITOR, owner_id)
        share = account.get_share_for_user(target)
        assert share is not None
        assert share.permission_level == PermissionLevel.EDITOR

    def test_editor_to_viewer(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.EDITOR, owner_id)
        account.collect_events()
        account.update_share_permission(target, PermissionLevel.VIEWER, owner_id)
        share = account.get_share_for_user(target)
        assert share is not None
        assert share.permission_level == PermissionLevel.VIEWER

    def test_emits_event_with_old_and_new(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.VIEWER, owner_id)
        account.collect_events()
        account.update_share_permission(target, PermissionLevel.EDITOR, owner_id)
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountShareUpdated)
        assert event.old_permission == "VIEWER"
        assert event.new_permission == "EDITOR"
        assert event.updated_by == owner_id

    def test_refreshes_updated_at(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        share = account.share_with(target, PermissionLevel.VIEWER, owner_id)
        old_updated = share.updated_at
        account.update_share_permission(target, PermissionLevel.EDITOR, owner_id)
        assert share.updated_at >= old_updated

    def test_cannot_grant_owner_via_update(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.VIEWER, owner_id)
        with pytest.raises(CannotGrantOwnerError):
            account.update_share_permission(target, PermissionLevel.OWNER, owner_id)

    def test_cannot_modify_owner_share(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        with pytest.raises(CannotModifyOwnerShareError):
            account.update_share_permission(owner_id, PermissionLevel.EDITOR, owner_id)

    def test_non_owner_cannot_update(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        target = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.share_with(target, PermissionLevel.VIEWER, owner_id)
        with pytest.raises(InsufficientPermissionError):
            account.update_share_permission(target, PermissionLevel.EDITOR, editor)

    def test_share_not_found(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        with pytest.raises(ShareNotFoundError):
            account.update_share_permission(uuid.uuid4(), PermissionLevel.EDITOR, owner_id)


# -- revoke_share tests -------------------------------------------------------


class TestRevokeShare:
    def test_revokes_successfully(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.EDITOR, owner_id)
        account.collect_events()
        account.revoke_share(target, owner_id)
        assert account.get_share_for_user(target) is None

    def test_emits_event(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.EDITOR, owner_id)
        account.collect_events()
        account.revoke_share(target, owner_id)
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountShareRevoked)
        assert event.user_id == target
        assert event.revoked_by == owner_id

    def test_cannot_revoke_owner(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        with pytest.raises(CannotRevokeOwnerError):
            account.revoke_share(owner_id, owner_id)

    def test_non_owner_cannot_revoke(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        target = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.share_with(target, PermissionLevel.VIEWER, owner_id)
        with pytest.raises(InsufficientPermissionError):
            account.revoke_share(target, editor)

    def test_share_not_found(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        with pytest.raises(ShareNotFoundError):
            account.revoke_share(uuid.uuid4(), owner_id)

    def test_reshare_after_revoke(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        target = uuid.uuid4()
        account.share_with(target, PermissionLevel.VIEWER, owner_id)
        account.revoke_share(target, owner_id)
        share = account.share_with(target, PermissionLevel.EDITOR, owner_id)
        assert share.permission_level == PermissionLevel.EDITOR
        assert share.is_active()


# -- leave_share tests --------------------------------------------------------


class TestLeaveShare:
    def test_editor_leaves(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.collect_events()
        account.leave_share(editor)
        assert account.get_share_for_user(editor) is None

    def test_viewer_leaves(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        viewer = uuid.uuid4()
        account.share_with(viewer, PermissionLevel.VIEWER, owner_id)
        account.collect_events()
        account.leave_share(viewer)
        assert account.get_share_for_user(viewer) is None

    def test_emits_event(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.collect_events()
        account.leave_share(editor)
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountShareLeft)
        assert event.user_id == editor

    def test_owner_cannot_leave(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        with pytest.raises(CannotLeaveAsOwnerError):
            account.leave_share(owner_id)

    def test_share_not_found(self) -> None:
        account = _make_account()
        with pytest.raises(ShareNotFoundError):
            account.leave_share(uuid.uuid4())

    def test_no_access_after_leave(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.leave_share(editor)
        assert account.has_permission(editor, PermissionLevel.VIEWER) is False


# -- transfer_ownership tests -------------------------------------------------


class TestTransferOwnership:
    def test_transfers_successfully(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        new_owner = uuid.uuid4()
        account.share_with(new_owner, PermissionLevel.EDITOR, owner_id)
        account.collect_events()
        account.transfer_ownership(new_owner, owner_id)
        assert account.is_owner(new_owner)
        assert not account.is_owner(owner_id)

    def test_old_owner_becomes_editor(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        new_owner = uuid.uuid4()
        account.share_with(new_owner, PermissionLevel.EDITOR, owner_id)
        account.transfer_ownership(new_owner, owner_id)
        assert account.get_permission_level(owner_id) == PermissionLevel.EDITOR

    def test_new_owner_becomes_owner(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        new_owner = uuid.uuid4()
        account.share_with(new_owner, PermissionLevel.VIEWER, owner_id)
        account.transfer_ownership(new_owner, owner_id)
        assert account.get_permission_level(new_owner) == PermissionLevel.OWNER

    def test_emits_event(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        new_owner = uuid.uuid4()
        account.share_with(new_owner, PermissionLevel.EDITOR, owner_id)
        account.collect_events()
        account.transfer_ownership(new_owner, owner_id)
        events = account.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, AccountOwnershipTransferred)
        assert event.old_owner_id == owner_id
        assert event.new_owner_id == new_owner

    def test_both_shares_updated_at_refreshed(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        new_owner = uuid.uuid4()
        share = account.share_with(new_owner, PermissionLevel.EDITOR, owner_id)
        old_owner_share = account.get_owner()
        old_updated_new = share.updated_at
        old_updated_old = old_owner_share.updated_at
        account.transfer_ownership(new_owner, owner_id)
        assert share.updated_at >= old_updated_new
        assert old_owner_share.updated_at >= old_updated_old

    def test_cannot_transfer_to_self(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        with pytest.raises(AlreadyOwnerError):
            account.transfer_ownership(owner_id, owner_id)

    def test_target_must_have_share(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        with pytest.raises(ShareNotFoundError):
            account.transfer_ownership(uuid.uuid4(), owner_id)

    def test_non_owner_cannot_transfer(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        with pytest.raises(InsufficientPermissionError):
            account.transfer_ownership(editor, editor)

    def test_viewer_promoted_to_owner(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        viewer = uuid.uuid4()
        account.share_with(viewer, PermissionLevel.VIEWER, owner_id)
        account.transfer_ownership(viewer, owner_id)
        assert account.is_owner(viewer)

    def test_transfer_back_allowed(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        other = uuid.uuid4()
        account.share_with(other, PermissionLevel.EDITOR, owner_id)
        account.transfer_ownership(other, owner_id)
        # Transfer back
        account.transfer_ownership(owner_id, other)
        assert account.is_owner(owner_id)
