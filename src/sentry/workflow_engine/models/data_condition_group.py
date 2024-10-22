from django.db import models

from sentry.backup.scopes import RelocationScope
from sentry.db.models import DefaultFieldsModel, region_silo_model, sane_repr


@region_silo_model
class DataConditionGroup(DefaultFieldsModel):
    """
    A data group is a way to specify a group of conditions that must be met for a workflow action to execute
    """

    __relocation_scope__ = RelocationScope.Organization
    __repr__ = sane_repr("logic_type")

    class Type(models.TextChoices):
        ANY = "any"
        ALL = "all"

    logic_type = models.CharField(max_length=200, choices=Type.choices, default=Type.ANY)
    organization = models.ForeignKey("sentry.Organization", on_delete=models.CASCADE)

    def evaluate(self, value) -> bool:
        """
        TODO - ensure logic types are correct
        - add support for _all_ types not just booleans
        """
        results = []
        for condition in self.conditions.all():
            evaluation_result = condition.evaluate(value)

            if evaluation_result and self.logic_type == self.Type.ANY:
                return True
            else:
                results.append(evaluation_result)

        if self.logic_type == self.Type.ALL:
            return all(results)

        return False
