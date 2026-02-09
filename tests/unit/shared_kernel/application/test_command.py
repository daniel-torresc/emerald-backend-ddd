from dataclasses import FrozenInstanceError, dataclass

import pytest

from emerald.shared_kernel.application.dtos.commands import Command


class TestCommand:
    def test_command_is_frozen_dataclass(self):
        cmd = Command()
        with pytest.raises(FrozenInstanceError):
            cmd.foo = "bar"  # type: ignore[attr-defined]

    def test_subclass_can_add_fields(self):
        @dataclass(frozen=True)
        class DoSomething(Command):
            name: str
            value: int

        cmd = DoSomething(name="test", value=42)
        assert cmd.name == "test"
        assert cmd.value == 42

    def test_subclass_is_instance_of_command(self):
        @dataclass(frozen=True)
        class DoSomething(Command):
            name: str

        cmd = DoSomething(name="test")
        assert isinstance(cmd, Command)

    def test_subclass_is_frozen(self):
        @dataclass(frozen=True)
        class DoSomething(Command):
            name: str

        cmd = DoSomething(name="test")
        with pytest.raises(FrozenInstanceError):
            cmd.name = "other"  # type: ignore[misc]
