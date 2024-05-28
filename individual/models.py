from django.db import models

import core
from core.models import HistoryModel

from django.utils.translation import gettext_lazy as _


class Individual(HistoryModel):
    first_name = models.CharField(max_length=255, null=False)
    last_name = models.CharField(max_length=255, null=False)
    dob = core.fields.DateField(null=False)
    #TODO WHY the HistoryModel json_ext was not enough
    json_ext = models.JSONField(db_column="Json_ext", blank=True, default=dict)

    def __str__(self):
        return f'{self.first_name} {self.last_name}'

    class Meta:
        managed = True


class IndividualDataSourceUpload(HistoryModel):
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        TRIGGERED = 'TRIGGERED', _('Triggered')
        IN_PROGRESS = 'IN_PROGRESS', _('In progress')
        SUCCESS = 'SUCCESS', _('Success')
        PARTIAL_SUCCESS = 'PARTIAL_SUCCESS', _('Partial Success')
        WAITING_FOR_VERIFICATION = 'WAITING_FOR_VERIFICATION', _('WAITING_FOR_VERIFICATION')
        FAIL = 'FAIL', _('Fail')

    source_name = models.CharField(max_length=255, null=False)
    source_type = models.CharField(max_length=255, null=False)

    status = models.CharField(max_length=255, choices=Status.choices, default=Status.PENDING)
    error = models.JSONField(blank=True, default=dict)


class IndividualDataSource(HistoryModel):
    individual = models.ForeignKey(Individual, models.DO_NOTHING, blank=True, null=True)
    upload = models.ForeignKey(IndividualDataSourceUpload, models.DO_NOTHING, blank=True, null=True)
    validations = models.JSONField(blank=True, default=dict)


class IndividualDataUploadRecords(HistoryModel):
    data_upload = models.ForeignKey(IndividualDataSourceUpload, models.DO_NOTHING, null=False)
    workflow = models.CharField(max_length=50)

    def __str__(self):
        return f"Individual Import - {self.data_upload.source_name} {self.workflow} {self.date_created}"


class Group(HistoryModel):
    code = models.CharField(max_length=64, blank=False, null=False)
    json_ext = models.JSONField(db_column="Json_ext", blank=True, default=dict)


class GroupDataSource(HistoryModel):
    group = models.ForeignKey(Group, models.DO_NOTHING, blank=True, null=True)
    upload = models.ForeignKey(IndividualDataSourceUpload, models.DO_NOTHING, blank=True, null=True)
    validations = models.JSONField(blank=True, default=dict)


class GroupIndividual(HistoryModel):
    class Role(models.TextChoices):
        HEAD = 'HEAD', _('HEAD')
        SPOUSE = 'SPOUSE', _('SPOUSE')
        SON = 'SON', _('SON')
        DAUGHTER = 'DAUGHTER', _('DAUGHTER')
        GRANDFATHER = 'GRANDFATHER', _('GRANDFATHER')
        GRANDMOTHER = 'GRANDMOTHER', _('GRANDMOTHER')
        MOTHER = 'MOTHER', _('MOTHER')
        FATHER = 'FATHER', _('FATHER')

    class RecipientType(models.TextChoices):
        PRIMARY = 'PRIMARY', _('PRIMARY')
        SECONDARY = 'SECONDARY', _('SECONDARY')

    group = models.ForeignKey(Group, models.DO_NOTHING)
    individual = models.ForeignKey(Individual, models.DO_NOTHING)
    role = models.CharField(max_length=255, choices=Role.choices, null=True, blank=True)
    recipient_type = models.CharField(max_length=255, choices=RecipientType.choices, null=True, blank=True)

    json_ext = models.JSONField(db_column="Json_ext", blank=True, default=dict)

    def save(self, *args, **kwargs):
        super().save(username=kwargs.get('username'))
        from individual.services import GroupAndGroupIndividualAlignmentService
        service = GroupAndGroupIndividualAlignmentService(self.user_updated)
        service.handle_head_change(self.id, self.role, self.group_id)
        service.handle_assure_primary_recipient_in_group(self.group, self.recipient_type)
        service.update_json_ext_for_group(self.group)
