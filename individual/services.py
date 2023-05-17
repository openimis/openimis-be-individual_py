import logging

from core.services import BaseService
from individual.models import Individual
from individual.validation import IndividualValidation

logger = logging.getLogger(__name__)


class IndividualService(BaseService):
    OBJECT_TYPE = Individual

    def __init__(self, user, validation_class=IndividualValidation):
        super().__init__(user, validation_class)
