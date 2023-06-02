from individual.models import Individual, IndividualDataSource, GroupIndividual, Group
from core.validation import BaseModelValidation


class IndividualValidation(BaseModelValidation):
    OBJECT_TYPE = Individual


class IndividualDataSourceValidation(BaseModelValidation):
    OBJECT_TYPE = IndividualDataSource


class GroupValidation(BaseModelValidation):
    OBJECT_TYPE = Group


class GroupIndividualValidation(BaseModelValidation):
    OBJECT_TYPE = GroupIndividual
