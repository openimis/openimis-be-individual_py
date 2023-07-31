from django.db import models

import core
from core.models import HistoryModel

from django.utils.translation import gettext_lazy as _


class Individual(HistoryModel):
    first_name = models.CharField(max_length=255, null=False)
    last_name = models.CharField(max_length=255, null=False)
    dob = core.fields.DateField(null=False)

    json_ext = models.JSONField(db_column="Json_ext", default=dict)

    class Meta:
        managed = True


class IndividualDataSourceUpload(HistoryModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        TRIGGERED = 'TRIGGERED', _('Triggered')
        IN_PROGRESS = 'IN_PROGRESS', _('In progress')
        SUCCESS = 'SUCCESS', _('Success')
        FAIL = 'FAIL', _('Fail')

    source_name = models.CharField(max_length=255, null=False)
    source_type = models.CharField(max_length=255, null=False)

    status = models.CharField(max_length=255, choices=Status.choices, default=Status.PENDING)
    error = models.JSONField(default=dict)


class IndividualDataSource(HistoryModel):
    individual = models.ForeignKey(Individual, models.DO_NOTHING, null=True)
    upload = models.ForeignKey(IndividualDataSourceUpload, models.DO_NOTHING, null=True)


class Group(HistoryModel):
    json_ext = models.JSONField(db_column="Json_ext", default=dict)


class GroupIndividual(HistoryModel):
    class Role(models.TextChoices):
        HEAD = 'HEAD', _('HEAD')
        RECIPIENT = 'RECIPIENT', _('RECIPIENT')

    group = models.ForeignKey(Group, models.DO_NOTHING)
    individual = models.ForeignKey(Individual, models.DO_NOTHING)
    role = models.CharField(max_length=255, choices=Role.choices, default=Role.RECIPIENT)

    json_ext = models.JSONField(db_column="Json_ext", default=dict)
