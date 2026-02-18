from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork


class _ConcreteUnitOfWork(AbstractUnitOfWork):
    """Minimal concrete UoW for testing the base class behavior."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class TestAbstractUnitOfWork:
    async def test_context_manager_returns_self(self):
        uow = _ConcreteUnitOfWork()
        async with uow as ctx:
            assert ctx is uow

    async def test_rollback_called_on_exit_without_commit(self):
        uow = _ConcreteUnitOfWork()
        async with uow:
            pass  # no commit
        assert uow.rolled_back is True
        assert uow.committed is False

    async def test_explicit_commit(self):
        uow = _ConcreteUnitOfWork()
        async with uow:
            await uow.commit()
        assert uow.committed is True
        # rollback still called on __aexit__ — safe by default
        assert uow.rolled_back is True

    async def test_rollback_called_on_exception(self):
        uow = _ConcreteUnitOfWork()
        try:
            async with uow:
                raise ValueError("boom")
        except ValueError:
            pass
        assert uow.rolled_back is True
        assert uow.committed is False
