from dataclasses import dataclass

from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class LoginUser(Command):
    """Command to authenticate a user with email + password."""

    email: str
    password: str
    portal_context: str


@dataclass(frozen=True)
class RefreshAccessToken(Command):
    """Command to refresh an access token using a refresh token."""

    refresh_token: str


@dataclass(frozen=True)
class LogoutSession(Command):
    """Command to revoke a single session's refresh token."""

    refresh_token: str


@dataclass(frozen=True)
class LogoutAllSessions(Command):
    """Command to revoke all sessions for a user."""

    user_id: str


@dataclass(frozen=True)
class RequestPasswordReset(Command):
    """Command to request a password reset token."""

    email: str


@dataclass(frozen=True)
class SubmitPasswordReset(Command):
    """Command to submit a new password using a reset token."""

    reset_token: str
    new_password: str
