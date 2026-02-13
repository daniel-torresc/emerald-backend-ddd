from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from emerald.core_finance.domain.models.value_objects.import_source import (
    ImportSource,
)
from emerald.core_finance.domain.models.value_objects.import_source_type import (
    ImportSourceType,
)
from emerald.shared_kernel.domain.exceptions import InvalidValueError


class TestImportSourceCreation:
    def test_valid_creation_with_all_fields(self) -> None:
        now = datetime.now(UTC)
        source = ImportSource(
            source_type=ImportSourceType.BANK_IMPORT,
            source_id="conn-123",
            imported_at=now,
        )
        assert source.source_type == ImportSourceType.BANK_IMPORT
        assert source.source_id == "conn-123"
        assert source.imported_at == now

    def test_valid_creation_with_source_id_none(self) -> None:
        now = datetime.now(UTC)
        source = ImportSource(
            source_type=ImportSourceType.MANUAL,
            source_id=None,
            imported_at=now,
        )
        assert source.source_id is None


class TestImportSourceValidation:
    def test_naive_datetime_raises_invalid_value_error(self) -> None:
        naive = datetime(2024, 1, 15, 12, 0, 0)  # noqa: DTZ001
        with pytest.raises(InvalidValueError, match="timezone-aware"):
            ImportSource(
                source_type=ImportSourceType.MANUAL,
                source_id=None,
                imported_at=naive,
            )

    def test_source_id_trimmed(self) -> None:
        source = ImportSource(
            source_type=ImportSourceType.BANK_IMPORT,
            source_id="  conn-456  ",
            imported_at=datetime.now(UTC),
        )
        assert source.source_id == "conn-456"

    def test_empty_source_id_after_trim_raises(self) -> None:
        with pytest.raises(InvalidValueError, match="non-empty"):
            ImportSource(
                source_type=ImportSourceType.BANK_IMPORT,
                source_id="",
                imported_at=datetime.now(UTC),
            )

    def test_whitespace_only_source_id_raises(self) -> None:
        with pytest.raises(InvalidValueError, match="non-empty"):
            ImportSource(
                source_type=ImportSourceType.BANK_IMPORT,
                source_id="   ",
                imported_at=datetime.now(UTC),
            )


class TestImportSourceFrozen:
    def test_cannot_mutate_source_type(self) -> None:
        source = ImportSource(
            source_type=ImportSourceType.MANUAL,
            source_id=None,
            imported_at=datetime.now(UTC),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            source.source_type = ImportSourceType.API  # type: ignore[misc]

    def test_cannot_mutate_source_id(self) -> None:
        source = ImportSource(
            source_type=ImportSourceType.MANUAL,
            source_id=None,
            imported_at=datetime.now(UTC),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            source.source_id = "new"  # type: ignore[misc]

    def test_cannot_mutate_imported_at(self) -> None:
        source = ImportSource(
            source_type=ImportSourceType.MANUAL,
            source_id=None,
            imported_at=datetime.now(UTC),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            source.imported_at = datetime.now(UTC)  # type: ignore[misc]
