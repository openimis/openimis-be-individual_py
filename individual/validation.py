import json
import re

import pandas as pd
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

from individual.apps import IndividualConfig
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


# `decimal` and `date` are filter-wizard types, not JSON Schema ones: checked as their
# closest JSON Schema type, so the rest of the schema is still validated as draft 7.
_JSON_SCHEMA_TYPE_OF_FILTER_TYPE = {'decimal': 'number', 'date': 'string'}


def schema_dict(value):
    """A stored schema as a dict - some rows hold it as a JSON string - or None."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    return value if isinstance(value, dict) else None


def filter_schema_json_errors(schema):
    """`core.utils.validate_json_schema`, accepting the filter-wizard types on properties."""
    properties = schema.get('properties')
    if isinstance(properties, dict):
        schema = {**schema, 'properties': {
            name: _as_json_schema_property(definition) for name, definition in properties.items()
        }}
    return validate_json_schema(schema)


def _as_json_schema_property(definition):
    field_type = definition.get('type') if isinstance(definition, dict) else None
    if isinstance(field_type, str) and field_type in _JSON_SCHEMA_TYPE_OF_FILTER_TYPE:
        return {**definition, 'type': _JSON_SCHEMA_TYPE_OF_FILTER_TYPE[field_type]}
    return definition


def _type_of(definition):
    return definition.get('type') if isinstance(definition, dict) else None


def _names(names):
    return ", ".join(map(str, names))


def _is_invalid_field_name(name):
    # A name becomes `json_ext__<name>__<lookup>` and travels in `<field>__<lookup>__<type>=<value>`
    # filter strings: `__`, a trailing `_` or `=` would split it in the wrong place.
    return not name or '__' in name or name.endswith('_') or '=' in name


def schema_errors(schema):
    """
    Rules shared by the individual, label and benefit plan schemas: JSON Schema draft 7,
    types the advanced filters handle, and the property options the upload validation reads.
    """
    if not isinstance(schema, dict):
        return [_message("individual.validation.schema.not_object")]
    errors = filter_schema_json_errors(schema)
    properties = schema.get('properties', {})
    if not isinstance(properties, dict):
        return errors + [_message("individual.validation.schema.not_object", 'properties')]

    supported = CustomFilterWizardInterface.FILTERS_BASED_ON_FIELD_TYPE
    definitions = {name: definition for name, definition in properties.items() if isinstance(definition, dict)}
    checks = [
        ("individual.validation.schema.invalid_name", [name for name in properties if _is_invalid_field_name(name)]),
        ("individual.validation.schema.unsupported_type", [
            name for name, definition in properties.items()
            if not isinstance(_type_of(definition), str) or _type_of(definition) not in supported
        ]),
        ("individual.validation.schema.invalid_description", [
            name for name, definition in definitions.items()
            if 'description' in definition and not isinstance(definition['description'], str)
        ]),
        # The upload validation tests the key's presence, so `false` would still mean unique.
        ("individual.validation.schema.invalid_uniqueness", [
            name for name, definition in definitions.items()
            if 'uniqueness' in definition and definition['uniqueness'] is not True
        ]),
        ("individual.validation.schema.invalid_calculation", [
            name for name, definition in definitions.items()
            if 'validationCalculation' in definition
            and not _is_named_calculation(definition['validationCalculation'])
        ]),
    ]
    return errors + [_message(key, _names(names)) for key, names in checks if names]


def _is_named_calculation(calculation):
    return isinstance(calculation, dict) and isinstance(calculation.get('name'), str) and bool(calculation['name'])


def schema_subset_errors(schema, system_properties=None):
    """Every property of `schema` must be a field of the system-wide schema, with the same type."""
    properties = (schema_dict(schema) or {}).get('properties')
    if not isinstance(properties, dict):
        return []
    if system_properties is None:
        system_properties = json.loads(IndividualConfig.individual_schema or '{}').get('properties', {})
    checks = [
        ("individual.validation.schema.not_in_system_schema",
         [name for name in properties if name not in system_properties]),
        ("individual.validation.schema.type_differs", [
            name for name, definition in properties.items()
            if name in system_properties and _type_of(definition) != _type_of(system_properties[name])
        ]),
    ]
    return [_message(key, _names(names)) for key, names in checks if names]


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
        return schema_errors(schema) or schema_subset_errors(schema)


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
