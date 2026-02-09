from dataclasses import dataclass

from emerald.shared_kernel.application.dtos.commands import Command


@dataclass(frozen=True)
class InitiateOAuthLogin(Command):
    """Command to generate an authorization URL for a social provider."""

    provider_type: str
    redirect_uri: str


@dataclass(frozen=True)
class CompleteOAuthLogin(Command):
    """Command to exchange an authorization code for claims and authenticate."""

    provider_type: str
    code: str
    state: str
    redirect_uri: str


@dataclass(frozen=True)
class LinkAuthProviderViaOAuth(Command):
    """Command for an authenticated user to link a social provider."""

    user_id: str
    provider_type: str
    code: str
    state: str
    redirect_uri: str


@dataclass(frozen=True)
class UnlinkAuthProvider(Command):
    """Command to remove a linked provider from a user's account."""

    user_id: str
    provider_type: str


@dataclass(frozen=True)
class SetOnboardingUsername(Command):
    """Command to set the username after social registration."""

    user_id: str
    username: str
