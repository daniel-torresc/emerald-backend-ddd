from emerald.core_finance.domain.exceptions import (
    AccountNameAlreadyExistsError,
    AccountNotFoundError,
    InvalidAccountNameError,
    InvalidAccountNotesError,
    InvalidIBANError,
    InvalidUserReferenceError,
)
from emerald.shared_kernel.domain.exceptions import (
    AlreadyExistsError,
    InvalidValueError,
    NotFoundError,
)


class TestInvalidAccountNameError:
    def test_hierarchy(self) -> None:
        assert issubclass(InvalidAccountNameError, InvalidValueError)

    def test_default_code(self) -> None:
        err = InvalidAccountNameError()
        assert err.code == "INVALID_ACCOUNT_NAME"

    def test_custom_message(self) -> None:
        err = InvalidAccountNameError("too long")
        assert err.message == "too long"


class TestInvalidIBANError:
    def test_hierarchy(self) -> None:
        assert issubclass(InvalidIBANError, InvalidValueError)

    def test_default_code(self) -> None:
        err = InvalidIBANError()
        assert err.code == "INVALID_IBAN"


class TestInvalidAccountNotesError:
    def test_hierarchy(self) -> None:
        assert issubclass(InvalidAccountNotesError, InvalidValueError)

    def test_default_code(self) -> None:
        err = InvalidAccountNotesError()
        assert err.code == "INVALID_ACCOUNT_NOTES"


class TestInvalidUserReferenceError:
    def test_hierarchy(self) -> None:
        assert issubclass(InvalidUserReferenceError, InvalidValueError)

    def test_default_code(self) -> None:
        err = InvalidUserReferenceError()
        assert err.code == "INVALID_USER_REFERENCE"


class TestAccountNameAlreadyExistsError:
    def test_hierarchy(self) -> None:
        assert issubclass(AccountNameAlreadyExistsError, AlreadyExistsError)

    def test_default_code(self) -> None:
        err = AccountNameAlreadyExistsError()
        assert err.code == "ACCOUNT_NAME_ALREADY_EXISTS"


class TestAccountNotFoundError:
    def test_hierarchy(self) -> None:
        assert issubclass(AccountNotFoundError, NotFoundError)

    def test_default_code(self) -> None:
        err = AccountNotFoundError()
        assert err.code == "ACCOUNT_NOT_FOUND"
