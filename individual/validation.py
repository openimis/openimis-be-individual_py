from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

from individual.models import Individual, IndividualDataSource, GroupIndividual, Group
from core.validation import BaseModelValidation, ObjectExistsValidationMixin
from tasks_management.models import Task


class IndividualValidation(BaseModelValidation, ObjectExistsValidationMixin):
    OBJECT_TYPE = Individual

    @classmethod
    def validate_undo_delete(cls, data):
        errors = []
        individual_id = data.get('id')
        cls.validate_object_exists(individual_id)
        is_deleted = Individual.objects.filter(id=individual_id, is_deleted=True).exists()
        if not is_deleted:
            errors += [_("individual.validation.validate_undo_delete.individual_not_deleted") % {
                'id': individual_id
            }]

        return errors


class IndividualDataSourceValidation(BaseModelValidation):
    OBJECT_TYPE = IndividualDataSource


class GroupValidation(BaseModelValidation):
    OBJECT_TYPE = Group
    # TODO: validate group code unique


class CrateGroupAndMoveIndividualValidation:
    @classmethod
    def validate_create_group_and_move_individual(cls, user, **data):
        GroupValidation().validate_create(user, **data)
        errors = []
        group_individual_id = data.get('group_individual_id')
        group_individual = GroupIndividual.objects.filter(id=group_individual_id).first()

        if not group_individual:
            errors += [_("individual.validation.validate_create_group_and_individual.group_individual_does_not_exist")]

        return errors


class GroupIndividualValidation(BaseModelValidation):
    OBJECT_TYPE = GroupIndividual

    @classmethod
    def validate_create(cls, user, **data):
        errors = [
            *check_if_group_id(data)
        ]
        if errors:
            raise ValidationError(errors)

    @classmethod
    def validate_update(cls, user, **data):
        errors = [
            *check_if_group_id(data),
            *validate_group_task_pending(data)
        ]
        if errors:
            raise ValidationError(errors)


def check_if_group_id(data):
    group_id = data.get('group_id')

    if group_id:
        return []

    return [{"message": _("individual.validation.check_if_group_id")}]


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
