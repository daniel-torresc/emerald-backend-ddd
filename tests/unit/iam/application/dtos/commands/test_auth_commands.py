import dataclasses

from emerald.iam.application.dtos.commands import (
    LoginUser,
    LogoutAllSessions,
    LogoutSession,
    RefreshAccessToken,
    RequestPasswordReset,
    SubmitPasswordReset,
)
from emerald.shared_kernel.application.dtos.commands import Command

# -- LoginUser -----------------------------------------------------------------


def test_login_user_is_frozen_dataclass():
    cmd = LoginUser(email="a@b.com", password="secret", portal_context="REGULAR")
    assert dataclasses.is_dataclass(cmd)
    assert cmd.__dataclass_params__.frozen is True


def test_login_user_extends_command():
    cmd = LoginUser(email="a@b.com", password="secret", portal_context="REGULAR")
    assert isinstance(cmd, Command)


def test_login_user_carries_primitives():
    cmd = LoginUser(email="a@b.com", password="secret", portal_context="REGULAR")
    assert cmd.email == "a@b.com"
    assert cmd.password == "secret"
    assert cmd.portal_context == "REGULAR"


def test_login_user_includes_portal_context_field():
    fields = {f.name for f in dataclasses.fields(LoginUser)}
    assert "portal_context" in fields


# -- RefreshAccessToken --------------------------------------------------------


def test_refresh_access_token_is_frozen_dataclass():
    cmd = RefreshAccessToken(refresh_token="tok")
    assert dataclasses.is_dataclass(cmd)
    assert cmd.__dataclass_params__.frozen is True


def test_refresh_access_token_extends_command():
    cmd = RefreshAccessToken(refresh_token="tok")
    assert isinstance(cmd, Command)


def test_refresh_access_token_carries_primitives():
    cmd = RefreshAccessToken(refresh_token="tok")
    assert cmd.refresh_token == "tok"


# -- LogoutSession -------------------------------------------------------------


def test_logout_session_is_frozen_dataclass():
    cmd = LogoutSession(refresh_token="tok")
    assert dataclasses.is_dataclass(cmd)
    assert cmd.__dataclass_params__.frozen is True


def test_logout_session_extends_command():
    cmd = LogoutSession(refresh_token="tok")
    assert isinstance(cmd, Command)


def test_logout_session_carries_primitives():
    cmd = LogoutSession(refresh_token="tok")
    assert cmd.refresh_token == "tok"


# -- LogoutAllSessions ---------------------------------------------------------


def test_logout_all_sessions_is_frozen_dataclass():
    cmd = LogoutAllSessions(user_id="abc-123")
    assert dataclasses.is_dataclass(cmd)
    assert cmd.__dataclass_params__.frozen is True


def test_logout_all_sessions_extends_command():
    cmd = LogoutAllSessions(user_id="abc-123")
    assert isinstance(cmd, Command)


def test_logout_all_sessions_carries_primitives():
    cmd = LogoutAllSessions(user_id="abc-123")
    assert cmd.user_id == "abc-123"


# -- RequestPasswordReset ------------------------------------------------------


def test_request_password_reset_is_frozen_dataclass():
    cmd = RequestPasswordReset(email="a@b.com")
    assert dataclasses.is_dataclass(cmd)
    assert cmd.__dataclass_params__.frozen is True


def test_request_password_reset_extends_command():
    cmd = RequestPasswordReset(email="a@b.com")
    assert isinstance(cmd, Command)


def test_request_password_reset_carries_primitives():
    cmd = RequestPasswordReset(email="a@b.com")
    assert cmd.email == "a@b.com"


# -- SubmitPasswordReset -------------------------------------------------------


def test_submit_password_reset_is_frozen_dataclass():
    cmd = SubmitPasswordReset(reset_token="tok", new_password="NewPass123!")
    assert dataclasses.is_dataclass(cmd)
    assert cmd.__dataclass_params__.frozen is True


def test_submit_password_reset_extends_command():
    cmd = SubmitPasswordReset(reset_token="tok", new_password="NewPass123!")
    assert isinstance(cmd, Command)


def test_submit_password_reset_carries_primitives():
    cmd = SubmitPasswordReset(reset_token="tok", new_password="NewPass123!")
    assert cmd.reset_token == "tok"
    assert cmd.new_password == "NewPass123!"
