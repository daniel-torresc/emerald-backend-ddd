from emerald.classification.domain.exceptions import (
    CannotBeOwnParentError,
    CircularReferenceError,
    IncompleteReorderError,
    InvalidTaxonomyNameError,
    InvalidTermNameError,
    MaxTermsExceededError,
    ParentTermDeletedError,
    ParentTermNotFoundError,
    TaxonomyDescriptionTooLongError,
    TaxonomyNameAlreadyExistsError,
    TaxonomyNotActiveError,
    TaxonomyNotFoundError,
    TermDescriptionTooLongError,
    TermNameAlreadyExistsError,
    TermNotFoundError,
)
from emerald.shared_kernel.domain.exceptions import (
    InvalidValueError,
    InvariantViolationError,
    NotFoundError,
)


class TestValueObjectErrors:
    def test_invalid_taxonomy_name_error(self) -> None:
        err = InvalidTaxonomyNameError()
        assert err.code == "INVALID_TAXONOMY_NAME"
        assert isinstance(err, InvalidValueError)

    def test_invalid_taxonomy_name_error_custom_message(self) -> None:
        err = InvalidTaxonomyNameError("custom msg")
        assert str(err) == "custom msg"

    def test_invalid_term_name_error(self) -> None:
        err = InvalidTermNameError()
        assert err.code == "INVALID_TERM_NAME"
        assert isinstance(err, InvalidValueError)

    def test_taxonomy_description_too_long_error(self) -> None:
        err = TaxonomyDescriptionTooLongError()
        assert err.code == "TAXONOMY_DESCRIPTION_TOO_LONG"
        assert isinstance(err, InvalidValueError)

    def test_term_description_too_long_error(self) -> None:
        err = TermDescriptionTooLongError()
        assert err.code == "TERM_DESCRIPTION_TOO_LONG"
        assert isinstance(err, InvalidValueError)


class TestInvariantErrors:
    def test_taxonomy_name_already_exists_error(self) -> None:
        err = TaxonomyNameAlreadyExistsError()
        assert err.code == "TAXONOMY_NAME_ALREADY_EXISTS"
        assert isinstance(err, InvariantViolationError)

    def test_term_name_already_exists_error(self) -> None:
        err = TermNameAlreadyExistsError()
        assert err.code == "TERM_NAME_ALREADY_EXISTS"
        assert isinstance(err, InvariantViolationError)

    def test_term_not_found_error(self) -> None:
        err = TermNotFoundError()
        assert err.code == "TERM_NOT_FOUND"
        assert isinstance(err, InvariantViolationError)

    def test_parent_term_not_found_error(self) -> None:
        err = ParentTermNotFoundError()
        assert err.code == "PARENT_TERM_NOT_FOUND"
        assert isinstance(err, InvariantViolationError)

    def test_parent_term_deleted_error(self) -> None:
        err = ParentTermDeletedError()
        assert err.code == "PARENT_TERM_DELETED"
        assert isinstance(err, InvariantViolationError)

    def test_cannot_be_own_parent_error(self) -> None:
        err = CannotBeOwnParentError()
        assert err.code == "CANNOT_BE_OWN_PARENT"
        assert isinstance(err, InvariantViolationError)

    def test_circular_reference_error(self) -> None:
        err = CircularReferenceError()
        assert err.code == "CIRCULAR_REFERENCE"
        assert isinstance(err, InvariantViolationError)

    def test_taxonomy_not_active_error(self) -> None:
        err = TaxonomyNotActiveError()
        assert err.code == "TAXONOMY_NOT_ACTIVE"
        assert isinstance(err, InvariantViolationError)

    def test_max_terms_exceeded_error(self) -> None:
        err = MaxTermsExceededError()
        assert err.code == "MAX_TERMS_EXCEEDED"
        assert isinstance(err, InvariantViolationError)

    def test_incomplete_reorder_error(self) -> None:
        err = IncompleteReorderError()
        assert err.code == "INCOMPLETE_REORDER"
        assert isinstance(err, InvariantViolationError)


class TestNotFoundErrors:
    def test_taxonomy_not_found_error(self) -> None:
        err = TaxonomyNotFoundError()
        assert err.code == "TAXONOMY_NOT_FOUND"
        assert isinstance(err, NotFoundError)

    def test_taxonomy_not_found_error_custom_message(self) -> None:
        err = TaxonomyNotFoundError("No such taxonomy")
        assert str(err) == "No such taxonomy"
