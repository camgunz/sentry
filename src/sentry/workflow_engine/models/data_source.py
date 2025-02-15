import dataclasses
from typing import Generic, TypeVar

from django.db import models

from sentry.backup.scopes import RelocationScope
from sentry.db.models import (
    BoundedBigIntegerField,
    DefaultFieldsModel,
    FlexibleForeignKey,
    region_silo_model,
)
from sentry.workflow_engine.models.data_source_detector import DataSourceDetector

T = TypeVar("T")


@dataclasses.dataclass
class DataPacket(Generic[T]):
    query_id: str
    packet: T


@region_silo_model
class DataSource(DefaultFieldsModel):
    __relocation_scope__ = RelocationScope.Organization

    class Type(models.IntegerChoices):
        SNUBA_QUERY_SUBSCRIPTION = 1
        SNUBA_QUERY = 2

    organization = FlexibleForeignKey("sentry.Organization")
    query_id = BoundedBigIntegerField()
    type = models.SmallIntegerField(choices=Type.choices)

    detectors = models.ManyToManyField("workflow_engine.Detector", through=DataSourceDetector)

    indexes = [
        models.Index(fields=("type", "query_id")),
        models.Index(fields=("organization", "type", "query_id")),
    ]
