import uuid

import pytest

from emerald.shared_kernel.domain.models.base.auditable import AuditableMixin


class _AuditableEntity(AuditableMixin):
    """Test helper that uses AuditableMixin."""

    pass


class TestAuditableCreation:
    def test_created_by_set_at_construction(self) -> None:
        actor = uuid.uuid4()
        e = _AuditableEntity(created_by=actor)
        assert e.created_by == actor

    def test_updated_by_defaults_to_created_by(self) -> None:
        actor = uuid.uuid4()
        e = _AuditableEntity(created_by=actor)
        assert e.updated_by == actor

    def test_explicit_updated_by(self) -> None:
        creator = uuid.uuid4()
        updater = uuid.uuid4()
        e = _AuditableEntity(created_by=creator, updated_by=updater)
        assert e.created_by == creator
        assert e.updated_by == updater


class TestAuditableImmutability:
    def test_created_by_is_immutable(self) -> None:
        actor = uuid.uuid4()
        e = _AuditableEntity(created_by=actor)
        with pytest.raises(AttributeError):
            e.created_by = uuid.uuid4()  # type: ignore[misc]


class TestAuditableUpdatedBy:
    def test_set_updated_by(self) -> None:
        actor = uuid.uuid4()
        new_actor = uuid.uuid4()
        e = _AuditableEntity(created_by=actor)
        e._set_updated_by(new_actor)
        assert e.updated_by == new_actor
        assert e.created_by == actor  # unchanged
