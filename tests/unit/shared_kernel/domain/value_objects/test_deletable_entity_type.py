from enum import Enum

from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)


class TestDeletableEntityTypeMembers:
    def test_is_enum(self) -> None:
        assert issubclass(DeletableEntityType, Enum)

    def test_has_exactly_eight_members(self) -> None:
        assert len(DeletableEntityType) == 8

    def test_each_value_matches_its_name(self) -> None:
        for member in DeletableEntityType:
            assert member.value == member.name

    def test_all_expected_members_present(self) -> None:
        expected = {
            "USER",
            "FINANCIAL_ACCOUNT",
            "TRANSACTION",
            "CARD",
            "ACCOUNT_SHARE",
            "TAXONOMY",
            "TAXONOMY_TERM",
            "BANK_CONNECTION",
        }
        actual = {m.name for m in DeletableEntityType}
        assert actual == expected

    def test_iterable(self) -> None:
        members = list(DeletableEntityType)
        assert len(members) == 8
        assert all(isinstance(m, DeletableEntityType) for m in members)
