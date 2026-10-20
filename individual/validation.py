import re

import pandas as pd
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

from individual.models import Individual, IndividualDataSource, IndividualLabel, GroupIndividual, Group
from core.custom_filters import CustomFilterWizardInterface
from core.utils import validate_json_schema
from core.validation import BaseModelValidation, ObjectExistsValidationMixin
from tasks_management.models import Task


class IndividualValidation(BaseModelValidation, ObjectExistsValidationMixin):
    OBJECT_TYPE = Individual

    @classmethod
    def validate_create(cls, user, **data):
        validate_individual_labels(data)

    @classmethod
    def validate_update(cls, user, **data):
        validate_individual_labels(data)

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


LABEL_CODE_PATTERN = re.compile(r'[A-Z][A-Z0-9_]{1,63}')
# pandas reads these cells as missing values, so an upload could never carry them.
RESERVED_LABEL_CODES = {'NA', 'NULL'}


def _message(key, detail=None):
    return {"message": f"{_(key)}: {detail}" if detail else _(key)}


def split_label_codes(value):
    """Label codes from a CSV cell: ';'-separated, exact match, empty or missing means none."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return []
    return [code for code in str(value).split(';') if code != '']


def validate_label_codes_exist(codes):
    """Must run inside a transaction: the rows stay locked so a concurrent delete cannot slip in."""
    known = set(
        IndividualLabel.objects.select_for_update()
        .filter(code__in=codes, is_deleted=False)
        .values_list('code', flat=True)
    )
    unknown = [code for code in codes if code not in known]
    if unknown:
        raise ValidationError([_message("individual.validation.labels.unknown", ", ".join(map(str, unknown)))])


def validate_individual_labels(data):
    labels = data.get('labels')
    if labels is None:
        return
    validate_label_codes_exist(labels)


def validate_bulk_label_change(add, remove):
    overlap = sorted(set(add) & set(remove), key=str)
    if overlap:
        raise ValidationError([
            _message("individual.validation.labels.add_remove_overlap", ", ".join(map(str, overlap)))
        ])
    validate_label_codes_exist([*add, *remove])


def label_schema_errors(schema):
    """JSON Schema draft 7, restricted to what the advanced-filter wizard can turn into filters."""
    if not isinstance(schema, dict):
        return [_message("individual.validation.label.schema_not_object")]
    errors = validate_json_schema(schema)
    properties = schema.get('properties', {})
    if not isinstance(properties, dict):
        return errors + [_message("individual.validation.label.schema_not_object", 'properties')]
    supported = CustomFilterWizardInterface.FILTERS_BASED_ON_FIELD_TYPE
    unsupported = [
        name for name, definition in properties.items()
        if not isinstance(definition, dict) or definition.get('type') not in supported
    ]
    if unsupported:
        errors.append(_message("individual.validation.label.schema_unsupported_type", ", ".join(unsupported)))
    return errors


class IndividualLabelValidation(BaseModelValidation):
    OBJECT_TYPE = IndividualLabel

    @classmethod
    def validate_create(cls, user, **data):
        code = data.get('code') or ''
        errors = []
        if not LABEL_CODE_PATTERN.fullmatch(code) or code in RESERVED_LABEL_CODES:
            errors.append(_message("individual.validation.label.invalid_code", code))
        elif IndividualLabel.objects.filter(code=code).exists():
            errors.append(_message("individual.validation.label.duplicate_code", code))
        errors += cls._schema_errors(data)
        if errors:
            raise ValidationError(errors)

    @classmethod
    def validate_update(cls, user, **data):
        label = IndividualLabel.objects.filter(id=data.get('id'), is_deleted=False).first()
        if not label:
            raise ValidationError([_message("individual.validation.label.not_found", data.get('id'))])
        errors = []
        if 'code' in data and data['code'] != label.code:
            errors.append(_message("individual.validation.label.code_immutable", label.code))
        errors += cls._schema_errors(data)
        if errors:
            raise ValidationError(errors)

    @classmethod
    def validate_delete(cls, user, **data):
        # Locked first, so an assignment that is checking this label waits and then sees it deleted.
        label = IndividualLabel.objects.select_for_update().filter(id=data.get('id')).first()
        if not label:
            raise ValidationError([_message("individual.validation.label.not_found", data.get('id'))])
        # Soft-deleted individuals count too: undoing their deletion must not bring back an unknown code.
        if Individual.objects.filter(labels__contains=[label.code]).exists():
            raise ValidationError([_message("individual.validation.label.in_use", label.code)])
        # Approving such a task would re-validate the labels, fail, and drop the whole edit.
        pending_task = Task.objects.filter(
            Q(status=Task.Status.RECEIVED) | Q(status=Task.Status.ACCEPTED),
            entity_type=ContentType.objects.get_for_model(Individual),
            data__incoming_data__labels__contains=[label.code],
        )
        if pending_task.exists():
            raise ValidationError([_message("individual.validation.label.in_pending_task", label.code)])

    @staticmethod
    def _schema_errors(data):
        schema = data.get('json_schema')
        if schema is None:
            return []
        return label_schema_errors(schema)


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
