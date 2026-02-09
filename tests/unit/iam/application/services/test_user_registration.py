import pytest

from emerald.iam.application.dtos.commands import RegisterUser
from emerald.iam.application.services.user_registration import UserRegistrationService
from emerald.iam.domain.events import UserRegistered
from emerald.iam.domain.exceptions import (
    EmailAlreadyExistsError,
    InvalidEmailError,
    InvalidUsernameError,
    PasswordTooWeakError,
    UsernameAlreadyExistsError,
)
from emerald.iam.domain.models import EmailAddress, HashedPassword, User, Username, UserStatus
from tests.unit.iam.fakes import FakeIamUnitOfWork, FakePasswordHasher


class TestUserRegistrationService:
    def _make_service(
        self,
    ) -> tuple[UserRegistrationService, FakeIamUnitOfWork, FakePasswordHasher]:
        uow = FakeIamUnitOfWork()
        hasher = FakePasswordHasher()
        service = UserRegistrationService(uow, hasher)
        return service, uow, hasher

    def _register_existing_user(self, uow: FakeIamUnitOfWork, email: str, username: str) -> User:
        """Helper: create and add a real User to the fake repository."""
        user = User.register(
            EmailAddress(email),
            Username(username),
            HashedPassword("hashed:SomePass123!!"),
        )
        user.collect_events()  # drain events so they don't leak into assertions
        uow.users.add(user)
        return user

    def test_successful_registration(self):
        service, uow, _ = self._make_service()
        user = service.register_user(RegisterUser("user@example.com", "johndoe", "ValidPass123!!"))
        assert isinstance(user, User)
        assert user.status == UserStatus.PENDING_VERIFICATION
        assert str(user.email) == "user@example.com"
        assert str(user.username) == "johndoe"
        assert user.password is not None
        assert user.password.hashed_value == "hashed:ValidPass123!!"

    def test_successful_registration_commits_uow(self):
        service, uow, _ = self._make_service()
        service.register_user(RegisterUser("user@example.com", "johndoe", "ValidPass123!!"))
        assert uow.committed is True

    def test_successful_registration_persists_user(self):
        service, uow, _ = self._make_service()
        user = service.register_user(RegisterUser("user@example.com", "johndoe", "ValidPass123!!"))
        assert uow.users.find_by_id(user.id) is not None

    def test_registration_emits_event(self):
        service, uow, _ = self._make_service()
        user = service.register_user(RegisterUser("user@example.com", "johndoe", "ValidPass123!!"))
        events = user.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], UserRegistered)

    def test_invalid_email_raises_before_uniqueness(self):
        service, uow, _ = self._make_service()
        with pytest.raises(InvalidEmailError):
            service.register_user(RegisterUser("invalid", "johndoe", "ValidPass123!!"))

    def test_invalid_username_raises_before_uniqueness(self):
        service, _, _ = self._make_service()
        with pytest.raises(InvalidUsernameError):
            service.register_user(RegisterUser("user@example.com", "ab", "ValidPass123!!"))

    def test_weak_password_raises_before_uniqueness(self):
        service, uow, _ = self._make_service()
        self._register_existing_user(uow, "user@example.com", "existing")
        with pytest.raises(PasswordTooWeakError):
            service.register_user(RegisterUser("user@example.com", "johndoe", "weak"))

    def test_duplicate_email_raises(self):
        service, uow, _ = self._make_service()
        self._register_existing_user(uow, "user@example.com", "existing")
        with pytest.raises(EmailAlreadyExistsError):
            service.register_user(RegisterUser("user@example.com", "johndoe", "ValidPass123!!"))

    def test_duplicate_username_raises(self):
        service, uow, _ = self._make_service()
        self._register_existing_user(uow, "other@example.com", "johndoe")
        with pytest.raises(UsernameAlreadyExistsError):
            service.register_user(RegisterUser("user@example.com", "johndoe", "ValidPass123!!"))

    def test_validation_order_format_before_strength(self):
        """Invalid format should fail before password strength is checked."""
        service, _, _ = self._make_service()
        with pytest.raises(InvalidEmailError):
            service.register_user(RegisterUser("bad", "johndoe", "weak"))

    def test_validation_order_strength_before_uniqueness(self):
        """Weak password should fail before uniqueness is checked."""
        service, uow, _ = self._make_service()
        self._register_existing_user(uow, "user@example.com", "existing")
        with pytest.raises(PasswordTooWeakError):
            service.register_user(RegisterUser("user@example.com", "johndoe", "short"))

    def test_email_normalized_before_uniqueness_check(self):
        service, uow, _ = self._make_service()
        self._register_existing_user(uow, "user@example.com", "existing")
        with pytest.raises(EmailAlreadyExistsError):
            service.register_user(RegisterUser("USER@EXAMPLE.COM", "johndoe", "ValidPass123!!"))

    def test_validation_failure_does_not_commit(self):
        """UoW should not be committed when validation fails."""
        service, uow, _ = self._make_service()
        with pytest.raises(InvalidEmailError):
            service.register_user(RegisterUser("invalid", "johndoe", "ValidPass123!!"))
        assert uow.committed is False
