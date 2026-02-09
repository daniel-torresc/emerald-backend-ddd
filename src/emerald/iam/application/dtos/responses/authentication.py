from dataclasses import dataclass


@dataclass(frozen=True)
class LoginResult:
    """Result of a successful login or token refresh."""

    access_token: str
    refresh_token: str
    expires_in: int
    is_new_registration: bool = False
