from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError
from individual.models import Individual, IndividualDataSource, GroupIndividual, Group
from core.validation import BaseModelValidation


class IndividualValidation(BaseModelValidation):
    OBJECT_TYPE = Individual


class IndividualDataSourceValidation(BaseModelValidation):
    OBJECT_TYPE = IndividualDataSource


class GroupValidation(BaseModelValidation):
    OBJECT_TYPE = Group

    def validate_update_group_individuals(cls, user, **data):
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

        super().validate_update(user, **data)


class GroupIndividualValidation(BaseModelValidation):
    OBJECT_TYPE = GroupIndividual
