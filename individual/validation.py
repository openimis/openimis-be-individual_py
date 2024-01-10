from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

from individual.models import Individual, IndividualDataSource, GroupIndividual, Group
from core.validation import BaseModelValidation
from tasks_management.models import Task


class IndividualValidation(BaseModelValidation):
    OBJECT_TYPE = Individual


class IndividualDataSourceValidation(BaseModelValidation):
    OBJECT_TYPE = IndividualDataSource


class GroupValidation(BaseModelValidation):
    OBJECT_TYPE = Group

    def validate_update_group_individuals(cls, user, **data):
        super().validate_update(user, **data)
        errors = []
        allowed_fields = {'id', 'individual_ids'}
        extra_fields = set(data.keys()) - allowed_fields
        missing_fields = allowed_fields - set(data.keys())

        if extra_fields:
            errors += [_("individual.validation.validate_update_group_individuals.extra_fields") % {
                'fields': {', '.join(extra_fields)}
            }]

        if missing_fields:
            errors += [_("individual.validation.validate_update_group_individuals.missing_fields") % {
                'fields': {', '.join(missing_fields)}
            }]

        if errors:
            raise ValidationError(errors)


class GroupIndividualValidation(BaseModelValidation):
    OBJECT_TYPE = GroupIndividual

    @classmethod
    def validate_update(cls, user, **data):
        errors = [
            *validate_group_task_pending(data)
        ]
        if errors:
            raise ValidationError(errors)


def validate_group_task_pending(data):
    group_id = data.get('group_id')
    content_type_groupindividual = ContentType.objects.get_for_model(GroupIndividual)
    content_type_group = ContentType.objects.get_for_model(Group)
    groupindividual_ids = list(GroupIndividual.objects.filter(group_id=group_id).values_list('id', flat=True))

    is_groupindividual_task = Task.objects.filter(
        Q(status=Task.Status.RECEIVED) | Q(status=Task.Status.ACCEPTED),
        entity_type=content_type_groupindividual,
        entity_id__in=groupindividual_ids,
    ).exists()

    is_group_task = Task.objects.filter(
        Q(status=Task.Status.RECEIVED) | Q(status=Task.Status.ACCEPTED),
        entity_type=content_type_group,
        entity_id=group_id,
    ).exists()

    if is_groupindividual_task or is_group_task:
        return [{"message": _("individual.validation.validate_group_task_pending") % {
            'group_id': group_id
        }}]
    return []
