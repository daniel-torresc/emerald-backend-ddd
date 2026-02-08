import dataclasses

import pytest

from emerald.iam.application.dto.auth_dtos import LoginResult


def test_login_result_is_frozen_dataclass():
    result = LoginResult(access_token="at", refresh_token="rt", expires_in=900)
    assert dataclasses.is_dataclass(result)
    assert result.__dataclass_params__.frozen is True


def test_login_result_fields():
    result = LoginResult(access_token="at", refresh_token="rt", expires_in=900)
    assert result.access_token == "at"
    assert result.refresh_token == "rt"
    assert result.expires_in == 900


def test_login_result_is_immutable():
    result = LoginResult(access_token="at", refresh_token="rt", expires_in=900)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.access_token = "modified"  # type: ignore[misc]


def test_login_result_is_immutable_refresh_token():
    result = LoginResult(access_token="at", refresh_token="rt", expires_in=900)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.refresh_token = "modified"  # type: ignore[misc]


def test_login_result_is_immutable_expires_in():
    result = LoginResult(access_token="at", refresh_token="rt", expires_in=900)
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.expires_in = 0  # type: ignore[misc]
