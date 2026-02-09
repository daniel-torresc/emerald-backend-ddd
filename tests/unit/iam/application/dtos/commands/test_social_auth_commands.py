import dataclasses

from emerald.iam.application.dtos.commands.social_auth import (
    CompleteOAuthLogin,
    InitiateOAuthLogin,
    LinkAuthProviderViaOAuth,
    SetOnboardingUsername,
    UnlinkAuthProvider,
)
from emerald.shared_kernel.application.dtos.commands import Command

# -- InitiateOAuthLogin --------------------------------------------------------


class TestInitiateOAuthLogin:
    def test_is_frozen_dataclass(self) -> None:
        cmd = InitiateOAuthLogin(provider_type="GOOGLE", redirect_uri="https://app/callback")
        assert dataclasses.is_dataclass(cmd)
        assert cmd.__dataclass_params__.frozen is True

    def test_extends_command(self) -> None:
        cmd = InitiateOAuthLogin(provider_type="GOOGLE", redirect_uri="https://app/callback")
        assert isinstance(cmd, Command)

    def test_carries_primitives(self) -> None:
        cmd = InitiateOAuthLogin(provider_type="GOOGLE", redirect_uri="https://app/callback")
        assert cmd.provider_type == "GOOGLE"
        assert cmd.redirect_uri == "https://app/callback"


# -- CompleteOAuthLogin --------------------------------------------------------


class TestCompleteOAuthLogin:
    def test_is_frozen_dataclass(self) -> None:
        cmd = CompleteOAuthLogin(
            provider_type="GOOGLE",
            code="auth-code-123",
            state="state-abc",
            redirect_uri="https://app/callback",
        )
        assert dataclasses.is_dataclass(cmd)
        assert cmd.__dataclass_params__.frozen is True

    def test_extends_command(self) -> None:
        cmd = CompleteOAuthLogin(
            provider_type="GOOGLE",
            code="auth-code-123",
            state="state-abc",
            redirect_uri="https://app/callback",
        )
        assert isinstance(cmd, Command)

    def test_carries_primitives(self) -> None:
        cmd = CompleteOAuthLogin(
            provider_type="GOOGLE",
            code="auth-code-123",
            state="state-abc",
            redirect_uri="https://app/callback",
        )
        assert cmd.provider_type == "GOOGLE"
        assert cmd.code == "auth-code-123"
        assert cmd.state == "state-abc"
        assert cmd.redirect_uri == "https://app/callback"


# -- LinkAuthProviderViaOAuth --------------------------------------------------


class TestLinkAuthProviderViaOAuth:
    def test_is_frozen_dataclass(self) -> None:
        cmd = LinkAuthProviderViaOAuth(
            user_id="user-abc",
            provider_type="MICROSOFT",
            code="code-456",
            state="state-xyz",
            redirect_uri="https://app/callback",
        )
        assert dataclasses.is_dataclass(cmd)
        assert cmd.__dataclass_params__.frozen is True

    def test_extends_command(self) -> None:
        cmd = LinkAuthProviderViaOAuth(
            user_id="user-abc",
            provider_type="MICROSOFT",
            code="code-456",
            state="state-xyz",
            redirect_uri="https://app/callback",
        )
        assert isinstance(cmd, Command)

    def test_carries_primitives(self) -> None:
        cmd = LinkAuthProviderViaOAuth(
            user_id="user-abc",
            provider_type="MICROSOFT",
            code="code-456",
            state="state-xyz",
            redirect_uri="https://app/callback",
        )
        assert cmd.user_id == "user-abc"
        assert cmd.provider_type == "MICROSOFT"
        assert cmd.code == "code-456"
        assert cmd.state == "state-xyz"
        assert cmd.redirect_uri == "https://app/callback"

    def test_has_all_expected_fields(self) -> None:
        fields = {f.name for f in dataclasses.fields(LinkAuthProviderViaOAuth)}
        assert fields == {"user_id", "provider_type", "code", "state", "redirect_uri"}


# -- UnlinkAuthProvider --------------------------------------------------------


class TestUnlinkAuthProvider:
    def test_is_frozen_dataclass(self) -> None:
        cmd = UnlinkAuthProvider(user_id="user-abc", provider_type="GOOGLE")
        assert dataclasses.is_dataclass(cmd)
        assert cmd.__dataclass_params__.frozen is True

    def test_extends_command(self) -> None:
        cmd = UnlinkAuthProvider(user_id="user-abc", provider_type="GOOGLE")
        assert isinstance(cmd, Command)

    def test_carries_primitives(self) -> None:
        cmd = UnlinkAuthProvider(user_id="user-abc", provider_type="GOOGLE")
        assert cmd.user_id == "user-abc"
        assert cmd.provider_type == "GOOGLE"


# -- SetOnboardingUsername -----------------------------------------------------


class TestSetOnboardingUsername:
    def test_is_frozen_dataclass(self) -> None:
        cmd = SetOnboardingUsername(user_id="user-abc", username="myname")
        assert dataclasses.is_dataclass(cmd)
        assert cmd.__dataclass_params__.frozen is True

    def test_extends_command(self) -> None:
        cmd = SetOnboardingUsername(user_id="user-abc", username="myname")
        assert isinstance(cmd, Command)

    def test_carries_primitives(self) -> None:
        cmd = SetOnboardingUsername(user_id="user-abc", username="myname")
        assert cmd.user_id == "user-abc"
        assert cmd.username == "myname"
