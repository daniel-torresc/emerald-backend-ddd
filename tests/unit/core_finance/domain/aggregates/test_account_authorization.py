import uuid
from decimal import Decimal

from emerald.core_finance.domain.models.aggregates.account import Account
from emerald.core_finance.domain.models.value_objects.account_name import AccountName
from emerald.core_finance.domain.models.value_objects.permission_level import PermissionLevel
from emerald.core_finance.domain.models.value_objects.user_reference import UserReference
from emerald.shared_kernel.domain.models.value_objects.currency import Currency
from emerald.shared_kernel.domain.models.value_objects.money import Money


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


class TestHasPermission:
    def test_owner_has_viewer(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        assert account.has_permission(owner_id, PermissionLevel.VIEWER) is True

    def test_owner_has_editor(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        assert account.has_permission(owner_id, PermissionLevel.EDITOR) is True

    def test_owner_has_owner(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        assert account.has_permission(owner_id, PermissionLevel.OWNER) is True

    def test_editor_has_viewer(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        assert account.has_permission(editor, PermissionLevel.VIEWER) is True

    def test_editor_has_editor(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        assert account.has_permission(editor, PermissionLevel.EDITOR) is True

    def test_editor_not_owner(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        assert account.has_permission(editor, PermissionLevel.OWNER) is False

    def test_viewer_has_viewer(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        viewer = uuid.uuid4()
        account.share_with(viewer, PermissionLevel.VIEWER, owner_id)
        assert account.has_permission(viewer, PermissionLevel.VIEWER) is True

    def test_viewer_not_editor(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        viewer = uuid.uuid4()
        account.share_with(viewer, PermissionLevel.VIEWER, owner_id)
        assert account.has_permission(viewer, PermissionLevel.EDITOR) is False

    def test_no_share_returns_false(self) -> None:
        account = _make_account()
        assert account.has_permission(uuid.uuid4(), PermissionLevel.VIEWER) is False

    def test_revoked_share_returns_false(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.revoke_share(editor, owner_id)
        assert account.has_permission(editor, PermissionLevel.VIEWER) is False

    def test_superadmin_with_no_share_denied(self) -> None:
        """SUPERADMIN has no special financial access without a share."""
        account = _make_account()
        superadmin_id = uuid.uuid4()
        assert account.has_permission(superadmin_id, PermissionLevel.VIEWER) is False


class TestConvenienceMethods:
    def test_is_owner_true_for_owner(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        assert account.is_owner(owner_id) is True

    def test_is_owner_false_for_editor(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        assert account.is_owner(editor) is False

    def test_can_edit_true_for_owner(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        assert account.can_edit(owner_id) is True

    def test_can_edit_true_for_editor(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        assert account.can_edit(editor) is True

    def test_can_edit_false_for_viewer(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        viewer = uuid.uuid4()
        account.share_with(viewer, PermissionLevel.VIEWER, owner_id)
        assert account.can_edit(viewer) is False

    def test_can_view_true_for_all_levels(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        viewer = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.share_with(viewer, PermissionLevel.VIEWER, owner_id)
        assert account.can_view(owner_id) is True
        assert account.can_view(editor) is True
        assert account.can_view(viewer) is True

    def test_can_view_false_for_no_share(self) -> None:
        account = _make_account()
        assert account.can_view(uuid.uuid4()) is False


class TestShareListingMethods:
    def test_get_active_shares_excludes_revoked(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        viewer = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        account.share_with(viewer, PermissionLevel.VIEWER, owner_id)
        account.revoke_share(viewer, owner_id)
        active = account.get_active_shares()
        assert len(active) == 2  # owner + editor
        user_ids = {s.user_id for s in active}
        assert owner_id in user_ids
        assert editor in user_ids
        assert viewer not in user_ids

    def test_get_owner_returns_owner_share(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        owner_share = account.get_owner()
        assert owner_share.user_id == owner_id
        assert owner_share.permission_level == PermissionLevel.OWNER

    def test_active_share_count_after_operations(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        assert account.active_share_count == 1
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        assert account.active_share_count == 2
        account.revoke_share(editor, owner_id)
        assert account.active_share_count == 1

    def test_get_share_for_user(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        share = account.get_share_for_user(editor)
        assert share is not None
        assert share.user_id == editor

    def test_get_share_for_user_returns_none(self) -> None:
        account = _make_account()
        assert account.get_share_for_user(uuid.uuid4()) is None

    def test_get_permission_level(self) -> None:
        owner_id = uuid.uuid4()
        account = _make_account(owner_id)
        editor = uuid.uuid4()
        account.share_with(editor, PermissionLevel.EDITOR, owner_id)
        assert account.get_permission_level(editor) == PermissionLevel.EDITOR
        assert account.get_permission_level(owner_id) == PermissionLevel.OWNER
        assert account.get_permission_level(uuid.uuid4()) is None
