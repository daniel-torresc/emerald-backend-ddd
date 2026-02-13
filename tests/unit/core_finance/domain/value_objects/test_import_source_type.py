from __future__ import annotations

from enum import Enum

from emerald.core_finance.domain.models.value_objects.import_source_type import (
    ImportSourceType,
)


class TestImportSourceTypeMembers:
    def test_manual_exists(self) -> None:
        assert ImportSourceType.MANUAL.value == "MANUAL"

    def test_bank_import_exists(self) -> None:
        assert ImportSourceType.BANK_IMPORT.value == "BANK_IMPORT"

    def test_bulk_import_exists(self) -> None:
        assert ImportSourceType.BULK_IMPORT.value == "BULK_IMPORT"

    def test_api_exists(self) -> None:
        assert ImportSourceType.API.value == "API"

    def test_has_exactly_four_members(self) -> None:
        assert len(ImportSourceType) == 4


class TestImportSourceTypeIsEnum:
    def test_is_enum(self) -> None:
        assert issubclass(ImportSourceType, Enum)

    def test_members_have_string_values(self) -> None:
        for member in ImportSourceType:
            assert isinstance(member.value, str)
