"""Shared kernel ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from emerald.shared_kernel.adapters.outbound.persistence.orm_base import Base
from emerald.shared_kernel.domain.models.entities.user_retention_preference import (
    UserRetentionPreference,
)
from emerald.shared_kernel.domain.models.value_objects.deletable_entity_type import (
    DeletableEntityType,
)
from emerald.shared_kernel.domain.models.value_objects.retention_period import (
    RetentionPeriod,
    RetentionUnit,
)


class UserRetentionPreferenceModel(Base):
    """ORM model for sk_user_retention_preferences table."""

    __tablename__ = "sk_user_retention_preferences"

    id: Mapped[uuid.UUID] = mapped_column(sa.Uuid, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        sa.Uuid,
        sa.ForeignKey("iam_users.id", ondelete="CASCADE"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    retention_duration: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    retention_unit: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "user_id", "entity_type", name="uq_sk_user_retention_preferences_user_entity"
        ),
    )

    @staticmethod
    def from_domain(preference: UserRetentionPreference) -> UserRetentionPreferenceModel:
        model = UserRetentionPreferenceModel()
        model.id = preference.id
        model.user_id = preference.user_id
        model.entity_type = preference.entity_type.value
        model.retention_duration = preference.retention_period.duration
        model.retention_unit = preference.retention_period.unit.value
        return model

    def to_domain(self) -> UserRetentionPreference:
        return UserRetentionPreference(
            id=self.id,
            user_id=self.user_id,
            entity_type=DeletableEntityType(self.entity_type),
            retention_period=RetentionPeriod(
                duration=self.retention_duration,
                unit=RetentionUnit(self.retention_unit),
            ),
        )
