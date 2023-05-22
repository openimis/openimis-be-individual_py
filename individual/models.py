from django.db import models

import core
from core.models import HistoryModel


class Individual(HistoryModel):
    first_name = models.CharField(max_length=255, null=False)
    last_name = models.CharField(max_length=255, null=False)
    dob = core.fields.DateField(null=False)

    class Meta:
        managed = True


class IndividualDataSource(HistoryModel):
    source_name = models.CharField(max_length=255, null=False)
    source_type = models.CharField(max_length=255, null=False)
    individual = models.ForeignKey(Individual, models.DO_NOTHING, null=True)
