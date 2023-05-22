from individual.models import Individual, IndividualDataSource
from core.validation import BaseModelValidation


class IndividualValidation(BaseModelValidation):
    OBJECT_TYPE = Individual


class IndividualDataSourceValidation(BaseModelValidation):
    OBJECT_TYPE = IndividualDataSource
