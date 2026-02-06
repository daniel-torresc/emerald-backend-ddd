import uuid

import pytest

from emerald.shared_kernel.entities import Entity


class TestEntityIdentity:
    def test_receives_uuid_at_construction(self) -> None:
        e = Entity()
        assert isinstance(e.id, uuid.UUID)

    def test_explicit_id(self) -> None:
        fixed_id = uuid.uuid4()
        e = Entity(id=fixed_id)
        assert e.id == fixed_id

    def test_id_is_immutable(self) -> None:
        e = Entity()
        with pytest.raises(AttributeError):
            e.id = uuid.uuid4()  # type: ignore[misc]


class TestEntityEquality:
    def test_same_id_are_equal(self) -> None:
        shared_id = uuid.uuid4()
        a = Entity(id=shared_id)
        b = Entity(id=shared_id)
        assert a == b

    def test_different_id_not_equal(self) -> None:
        a = Entity()
        b = Entity()
        assert a != b


class TestEntityHash:
    def test_is_hashable(self) -> None:
        e = Entity()
        assert isinstance(hash(e), int)

    def test_same_id_same_hash(self) -> None:
        shared_id = uuid.uuid4()
        a = Entity(id=shared_id)
        b = Entity(id=shared_id)
        assert hash(a) == hash(b)

    def test_usable_in_set(self) -> None:
        shared_id = uuid.uuid4()
        a = Entity(id=shared_id)
        b = Entity(id=shared_id)
        assert len({a, b}) == 1
