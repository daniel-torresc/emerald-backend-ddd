import pytest

from emerald.core_finance.domain.constants import (
    MAX_MERCHANT_LENGTH,
    MAX_USER_DESCRIPTION_LENGTH,
)
from emerald.core_finance.domain.exceptions.bulk_exceptions import EmptyBulkUpdateError
from emerald.core_finance.domain.exceptions.transaction_exceptions import (
    EmptyDescriptionError,
    InvalidMerchantError,
)
from emerald.core_finance.domain.models.value_objects.bulk_update_fields import (
    _UNSET,
    BulkUpdateFields,
    _UnsetType,
)
from emerald.core_finance.domain.models.value_objects.review_status import ReviewStatus


class TestUnsetSentinel:
    def test_identity(self) -> None:
        assert _UNSET is _UnsetType()

    def test_repr(self) -> None:
        assert repr(_UNSET) == "_UNSET"

    def test_bool_is_false(self) -> None:
        assert not _UNSET


class TestBulkUpdateFields:
    def test_valid_with_review_status(self) -> None:
        fields = BulkUpdateFields(review_status=ReviewStatus.REVIEWED)
        assert fields.review_status == ReviewStatus.REVIEWED
        assert isinstance(fields.user_description, _UnsetType)
        assert isinstance(fields.merchant, _UnsetType)

    def test_valid_with_user_description(self) -> None:
        fields = BulkUpdateFields(user_description="Updated desc")
        assert fields.user_description == "Updated desc"

    def test_valid_with_merchant(self) -> None:
        fields = BulkUpdateFields(merchant="New Merchant")
        assert fields.merchant == "New Merchant"

    def test_valid_with_all_fields(self) -> None:
        fields = BulkUpdateFields(
            review_status=ReviewStatus.REVIEWED,
            user_description="Desc",
            merchant="Merchant",
        )
        assert fields.review_status == ReviewStatus.REVIEWED
        assert fields.user_description == "Desc"
        assert fields.merchant == "Merchant"

    def test_all_unset_raises_empty_bulk_update(self) -> None:
        with pytest.raises(EmptyBulkUpdateError):
            BulkUpdateFields()

    def test_none_clears_user_description(self) -> None:
        fields = BulkUpdateFields(user_description=None)
        assert fields.user_description is None

    def test_none_clears_merchant(self) -> None:
        fields = BulkUpdateFields(merchant=None)
        assert fields.merchant is None

    def test_user_description_too_long_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            BulkUpdateFields(user_description="x" * (MAX_USER_DESCRIPTION_LENGTH + 1))

    def test_empty_user_description_raises(self) -> None:
        with pytest.raises(EmptyDescriptionError):
            BulkUpdateFields(user_description="   ")

    def test_merchant_too_long_raises(self) -> None:
        with pytest.raises(InvalidMerchantError):
            BulkUpdateFields(merchant="x" * (MAX_MERCHANT_LENGTH + 1))

    def test_empty_merchant_raises(self) -> None:
        with pytest.raises(InvalidMerchantError):
            BulkUpdateFields(merchant="   ")

    def test_user_description_trimmed(self) -> None:
        fields = BulkUpdateFields(user_description="  Trimmed  ")
        assert fields.user_description == "Trimmed"

    def test_merchant_trimmed(self) -> None:
        fields = BulkUpdateFields(merchant="  Store  ")
        assert fields.merchant == "Store"

    def test_frozen(self) -> None:
        fields = BulkUpdateFields(review_status=ReviewStatus.REVIEWED)
        with pytest.raises(AttributeError):
            fields.review_status = ReviewStatus.TO_REVIEW  # type: ignore[misc]
