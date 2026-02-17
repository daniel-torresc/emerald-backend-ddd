import uuid
from typing import Protocol


class TransactionAccessPort(Protocol):
    """Cross-context port for validating transaction state and account permissions.

    Defined in Classification, implemented by infrastructure (delegates to Core Finance).

    Methods:
        verify_transaction_active: Raises TransactionNotActiveError if not found or deleted.
        verify_editor_permission: Raises AuthorizationError if permission insufficient.
    """

    def verify_transaction_active(self, transaction_id: uuid.UUID) -> uuid.UUID:
        """Verify transaction exists and is active.

        Returns the transaction's account_id.
        Raises TransactionNotActiveError if not found or deleted.
        """
        ...

    def verify_editor_permission(self, account_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Verify user has at least EDITOR permission on the account.

        Raises AuthorizationError if permission is insufficient.
        """
        ...
