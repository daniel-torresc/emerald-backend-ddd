from emerald.shared_kernel.application.ports.outbound.unit_of_work import AbstractUnitOfWork


class _ConcreteUnitOfWork(AbstractUnitOfWork):
    """Minimal concrete UoW for testing the base class behavior."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class TestAbstractUnitOfWork:
    def test_context_manager_returns_self(self):
        uow = _ConcreteUnitOfWork()
        with uow as ctx:
            assert ctx is uow

    def test_rollback_called_on_exit_without_commit(self):
        uow = _ConcreteUnitOfWork()
        with uow:
            pass  # no commit
        assert uow.rolled_back is True
        assert uow.committed is False

    def test_explicit_commit(self):
        uow = _ConcreteUnitOfWork()
        with uow:
            uow.commit()
        assert uow.committed is True
        # rollback still called on __exit__ — safe by default
        assert uow.rolled_back is True

    def test_rollback_called_on_exception(self):
        uow = _ConcreteUnitOfWork()
        try:
            with uow:
                raise ValueError("boom")
        except ValueError:
            pass
        assert uow.rolled_back is True
        assert uow.committed is False
