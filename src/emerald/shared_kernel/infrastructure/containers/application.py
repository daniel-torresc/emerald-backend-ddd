"""Application container — root composition root wiring all bounded contexts."""

from __future__ import annotations

from dependency_injector import containers, providers

from emerald.iam.infrastructure.containers import IamContainer
from emerald.shared_kernel.infrastructure.containers.core import CoreContainer


class ApplicationContainer(containers.DeclarativeContainer):
    """Root composition root.

    Wires CoreContainer (shared kernel) and per-context containers.
    Additional bounded contexts will be added as their persistence adapters are built.
    """

    wiring_config = containers.WiringConfiguration(modules=[])

    core = providers.Container(CoreContainer)
    iam = providers.Container(IamContainer, core=core)
