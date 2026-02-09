from dataclasses import dataclass

from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class RegisterUser(Command):
    """Command to register a new user with email + password."""

    email: str
    username: str
    plaintext_password: str
