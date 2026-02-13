from __future__ import annotations

from enum import Enum

from emerald.core_finance.domain.models.value_objects.card_type import CardType


class TestCardTypeMembers:
    def test_credit_exists(self) -> None:
        assert CardType.CREDIT.value == "CREDIT"

    def test_debit_exists(self) -> None:
        assert CardType.DEBIT.value == "DEBIT"

    def test_has_exactly_two_members(self) -> None:
        assert len(CardType) == 2


class TestCardTypeIsEnum:
    def test_is_enum(self) -> None:
        assert issubclass(CardType, Enum)

    def test_members_have_string_values(self) -> None:
        for member in CardType:
            assert isinstance(member.value, str)
