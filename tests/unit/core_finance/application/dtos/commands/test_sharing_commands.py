import uuid

from emerald.core_finance.application.dtos.commands.sharing_commands import (
    LeaveAccountShare,
    RevokeAccountShare,
    ShareAccountWith,
    TransferAccountOwnership,
    UpdateSharePermission,
)
from emerald.shared_kernel.application.dtos.commands import Command


class TestShareAccountWith:
    def test_extends_command(self) -> None:
        assert issubclass(ShareAccountWith, Command)

    def test_frozen(self) -> None:
        cmd = ShareAccountWith(
            account_id=uuid.uuid4(),
            requesting_user_id=uuid.uuid4(),
            target_user_id=uuid.uuid4(),
            permission_level="EDITOR",
        )
        assert cmd.permission_level == "EDITOR"


class TestUpdateSharePermission:
    def test_extends_command(self) -> None:
        assert issubclass(UpdateSharePermission, Command)


class TestRevokeAccountShare:
    def test_extends_command(self) -> None:
        assert issubclass(RevokeAccountShare, Command)


class TestLeaveAccountShare:
    def test_extends_command(self) -> None:
        assert issubclass(LeaveAccountShare, Command)


class TestTransferAccountOwnership:
    def test_extends_command(self) -> None:
        assert issubclass(TransferAccountOwnership, Command)
