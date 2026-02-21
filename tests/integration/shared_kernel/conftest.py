"""Shared kernel integration test fixtures."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from emerald.shared_kernel.adapters.outbound.persistence.retention_policy_repository import (
    SqlAlchemyRetentionPolicyRepository,
)


@pytest.fixture
def retention_repo(session: AsyncSession) -> SqlAlchemyRetentionPolicyRepository:
    return SqlAlchemyRetentionPolicyRepository(session)
