from __future__ import annotations

from enum import Enum

from emerald.core_finance.domain.models.value_objects.card_network import CardNetwork


class TestCardNetworkMembers:
    def test_visa_exists(self) -> None:
        assert CardNetwork.VISA.value == "VISA"

    def test_mastercard_exists(self) -> None:
        assert CardNetwork.MASTERCARD.value == "MASTERCARD"

    def test_american_express_exists(self) -> None:
        assert CardNetwork.AMERICAN_EXPRESS.value == "AMERICAN_EXPRESS"

    def test_discover_exists(self) -> None:
        assert CardNetwork.DISCOVER.value == "DISCOVER"

    def test_other_exists(self) -> None:
        assert CardNetwork.OTHER.value == "OTHER"

    def test_has_exactly_five_members(self) -> None:
        assert len(CardNetwork) == 5


class TestCardNetworkIsEnum:
    def test_is_enum(self) -> None:
        assert issubclass(CardNetwork, Enum)

    def test_members_have_string_values(self) -> None:
        for member in CardNetwork:
            assert isinstance(member.value, str)
