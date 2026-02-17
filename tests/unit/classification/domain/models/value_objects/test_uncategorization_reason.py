from emerald.classification.domain.models.value_objects.uncategorization_reason import (
    UncategorizationReason,
)


class TestUncategorizationReason:
    def test_has_four_members(self) -> None:
        assert len(UncategorizationReason) == 4

    def test_manual(self) -> None:
        assert UncategorizationReason.MANUAL == "manual"

    def test_term_deleted(self) -> None:
        assert UncategorizationReason.TERM_DELETED == "term_deleted"

    def test_taxonomy_deleted(self) -> None:
        assert UncategorizationReason.TAXONOMY_DELETED == "taxonomy_deleted"

    def test_transaction_deleted(self) -> None:
        assert UncategorizationReason.TRANSACTION_DELETED == "transaction_deleted"

    def test_is_str_enum(self) -> None:
        assert isinstance(UncategorizationReason.MANUAL, str)
