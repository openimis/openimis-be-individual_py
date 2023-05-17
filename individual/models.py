from django.db import models

import core
from core.models import HistoryBusinessModel


class Individual(HistoryBusinessModel):
    first_name = models.CharField(db_column='FirstName', max_length=255, null=False)
    last_name = models.CharField(db_column='LastName', max_length=255, null=False)
    dob = core.fields.DateField(db_column='Dob', null=False)

    class Meta:
        managed = True
        db_table = 'tblIndividual'
