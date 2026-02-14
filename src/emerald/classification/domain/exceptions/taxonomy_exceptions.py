from emerald.shared_kernel.domain.exceptions import (
    InvalidValueError,
    InvariantViolationError,
    NotFoundError,
)

# -- Value object errors (extend InvalidValueError) ---------------------------


class InvalidTaxonomyNameError(InvalidValueError):
    """Taxonomy name is empty or exceeds maximum length."""

    def __init__(
        self, message: str = "Invalid taxonomy name", code: str = "INVALID_TAXONOMY_NAME"
    ) -> None:
        super().__init__(message, code)


class InvalidTermNameError(InvalidValueError):
    """Term name is empty or exceeds maximum length."""

    def __init__(self, message: str = "Invalid term name", code: str = "INVALID_TERM_NAME") -> None:
        super().__init__(message, code)


class TaxonomyDescriptionTooLongError(InvalidValueError):
    """Taxonomy description exceeds maximum length."""

    def __init__(
        self,
        message: str = "Taxonomy description is too long",
        code: str = "TAXONOMY_DESCRIPTION_TOO_LONG",
    ) -> None:
        super().__init__(message, code)


class TermDescriptionTooLongError(InvalidValueError):
    """Term description exceeds maximum length."""

    def __init__(
        self,
        message: str = "Term description is too long",
        code: str = "TERM_DESCRIPTION_TOO_LONG",
    ) -> None:
        super().__init__(message, code)


# -- Invariant errors (extend InvariantViolationError) -------------------------


class TaxonomyNameAlreadyExistsError(InvariantViolationError):
    """Duplicate taxonomy name for the same user."""

    def __init__(
        self,
        message: str = "Taxonomy name already exists for this user",
        code: str = "TAXONOMY_NAME_ALREADY_EXISTS",
    ) -> None:
        super().__init__(message, code)


class TermNameAlreadyExistsError(InvariantViolationError):
    """Duplicate term name within a taxonomy."""

    def __init__(
        self,
        message: str = "Term name already exists in this taxonomy",
        code: str = "TERM_NAME_ALREADY_EXISTS",
    ) -> None:
        super().__init__(message, code)


class TermNotFoundError(InvariantViolationError):
    """Term does not exist or is deleted (context-dependent)."""

    def __init__(self, message: str = "Term not found", code: str = "TERM_NOT_FOUND") -> None:
        super().__init__(message, code)


class ParentTermNotFoundError(InvariantViolationError):
    """Parent term does not exist in taxonomy."""

    def __init__(
        self,
        message: str = "Parent term not found",
        code: str = "PARENT_TERM_NOT_FOUND",
    ) -> None:
        super().__init__(message, code)


class ParentTermDeletedError(InvariantViolationError):
    """Parent term is soft deleted."""

    def __init__(
        self,
        message: str = "Parent term is deleted",
        code: str = "PARENT_TERM_DELETED",
    ) -> None:
        super().__init__(message, code)


class CannotBeOwnParentError(InvariantViolationError):
    """Term cannot be moved under itself."""

    def __init__(
        self,
        message: str = "Term cannot be its own parent",
        code: str = "CANNOT_BE_OWN_PARENT",
    ) -> None:
        super().__init__(message, code)


class CircularReferenceError(InvariantViolationError):
    """Move would create a circular reference in the hierarchy."""

    def __init__(
        self,
        message: str = "Move would create a circular reference",
        code: str = "CIRCULAR_REFERENCE",
    ) -> None:
        super().__init__(message, code)


class TaxonomyNotActiveError(InvariantViolationError):
    """Operation attempted on a soft-deleted taxonomy."""

    def __init__(
        self,
        message: str = "Taxonomy is not active",
        code: str = "TAXONOMY_NOT_ACTIVE",
    ) -> None:
        super().__init__(message, code)


class MaxTermsExceededError(InvariantViolationError):
    """Term count has reached the maximum per taxonomy."""

    def __init__(
        self,
        message: str = "Maximum terms per taxonomy exceeded",
        code: str = "MAX_TERMS_EXCEEDED",
    ) -> None:
        super().__init__(message, code)


class IncompleteReorderError(InvariantViolationError):
    """Reorder does not include all siblings or has duplicates."""

    def __init__(
        self,
        message: str = "Reorder must include all active siblings with no duplicates",
        code: str = "INCOMPLETE_REORDER",
    ) -> None:
        super().__init__(message, code)


# -- Not found error (extends NotFoundError) -----------------------------------


class TaxonomyNotFoundError(NotFoundError):
    """Taxonomy not found in repository."""

    def __init__(
        self, message: str = "Taxonomy not found", code: str = "TAXONOMY_NOT_FOUND"
    ) -> None:
        super().__init__(message, code)
