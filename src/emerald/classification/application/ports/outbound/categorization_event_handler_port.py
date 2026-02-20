import uuid
from typing import Protocol


class CategorizationEventHandlerPort(Protocol):
    """Event handler protocol for lifecycle cascades.

    Defined in Classification. Implemented by TransactionCategorizationService.
    Called by other contexts/composition root when relevant events occur.
    """

    async def handle_term_deleted(self, term_id: uuid.UUID) -> int:
        """Remove all assignments referencing the deleted term.

        Returns count of removed assignments.
        """
        ...

    async def handle_taxonomy_soft_deleted(self, taxonomy_id: uuid.UUID) -> int:
        """Remove all assignments for any term in the deleted taxonomy.

        Returns count of removed assignments.
        """
        ...

    async def handle_transaction_soft_deleted(self, transaction_id: uuid.UUID) -> int:
        """Remove all assignments for the deleted transaction.

        Returns count of removed assignments.
        """
        ...
