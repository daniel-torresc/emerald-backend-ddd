from emerald.iam.application.dtos.commands import RegisterUser
from emerald.iam.application.ports.outbound.unit_of_work import AbstractIamUnitOfWork
from emerald.iam.domain.exceptions import EmailAlreadyExistsError, UsernameAlreadyExistsError
from emerald.iam.domain.models.aggregates.user import User
from emerald.iam.domain.models.value_objects.email_address import EmailAddress
from emerald.iam.domain.models.value_objects.hashed_password import HashedPassword
from emerald.iam.domain.models.value_objects.username import Username
from emerald.iam.domain.ports.password_hasher import PasswordHasher
from emerald.iam.domain.services.password_validation import validate_password_strength


class UserRegistrationService:
    """Application service coordinating user registration.

    Validation order: format -> strength -> uniqueness -> creation.
    """

    def __init__(self, uow: AbstractIamUnitOfWork, hasher: PasswordHasher) -> None:
        self._uow = uow
        self._hasher = hasher

    def register_user(self, cmd: RegisterUser) -> User:
        """Register a new user with email + password.

        Raises:
            InvalidEmailError: if email format is invalid
            InvalidUsernameError: if username format is invalid
            PasswordTooWeakError: if password doesn't meet strength requirements
            EmailAlreadyExistsError: if email is already in use
            UsernameAlreadyExistsError: if username is taken
        """
        with self._uow:
            # 1. Validate format (creates value objects which validate)
            email_vo = EmailAddress(cmd.email)
            username_vo = Username(cmd.username)

            # 2. Validate password strength
            validate_password_strength(cmd.plaintext_password)

            # 3. Check uniqueness
            if self._uow.users.exists_by_email(email_vo):
                raise EmailAlreadyExistsError(f"Email {email_vo} is already in use")
            if self._uow.users.exists_by_username(username_vo, include_recently_deleted=True):
                raise UsernameAlreadyExistsError(f"Username {username_vo} is already taken")

            # 4. Hash password
            hashed = self._hasher.hash(cmd.plaintext_password)
            hashed_password = HashedPassword(hashed)

            # 5. Create user and persist
            user = User.register(email_vo, username_vo, hashed_password)
            self._uow.users.add(user)
            self._uow.commit()

            return user
