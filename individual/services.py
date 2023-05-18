import logging

from core.services import BaseService
from core.signals import register_service_signal
from individual.models import Individual
from individual.validation import IndividualValidation

logger = logging.getLogger(__name__)


class IndividualService(BaseService):
    @register_service_signal('individual_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('individual_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('individual_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)

    OBJECT_TYPE = Individual

    def __init__(self, user, validation_class=IndividualValidation):
        super().__init__(user, validation_class)
