import logging

from django.db import transaction

from core.services import BaseService
from core.signals import register_service_signal
from individual.models import Individual, IndividualDataSource, GroupIndividual, Group
from individual.validation import IndividualValidation, IndividualDataSourceValidation, GroupIndividualValidation, \
    GroupValidation
from core.services.utils import check_authentication as check_authentication, output_exception

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


class IndividualDataSourceService(BaseService):
    @register_service_signal('individual_data_source_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('individual_data_source_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('individual_data_source_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)

    OBJECT_TYPE = IndividualDataSource

    def __init__(self, user, validation_class=IndividualDataSourceValidation):
        super().__init__(user, validation_class)


class GroupService(BaseService):
    OBJECT_TYPE = Group

    def __init__(self, user, validation_class=GroupValidation):
        super().__init__(user, validation_class)

    @register_service_signal('group_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('group_service.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('group_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


class GroupIndividualService(BaseService):
    OBJECT_TYPE = GroupIndividual

    def __init__(self, user, validation_class=GroupIndividualValidation):
        super().__init__(user, validation_class)

    @register_service_signal('group_individual_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('group_individual.update')
    def update(self, obj_data):
        return super().update(obj_data)

    @register_service_signal('group_individual.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)


class GroupFromMultipleIndividualsService(BaseService):
    OBJECT_TYPE = Group

    def __init__(self, user, validation_class=GroupValidation):
        super().__init__(user, validation_class)

    @check_authentication
    @register_service_signal('group_from_multiple_individuals_service.create')
    def create(self, obj_data):
        try:
            with transaction.atomic():
                individual_ids = obj_data.pop('individual_ids')
                group = GroupService(self.user).create(obj_data)
                group_id = group['data']['id']
                individual_ids_list = [GroupIndividualService(self.user).create({'group_id': group_id,
                                                                                 'individual_id': individual_id})
                                       for individual_id in individual_ids]
                group_and_individuals_dict = {**group, 'individuals': individual_ids_list}
                return group_and_individuals_dict
        except Exception as exc:
            return output_exception(model_name=self.OBJECT_TYPE.__name__, method="create", exception=exc)

    @register_service_signal('group_from_multiple_individuals_service.update')
    def update(self, obj_data):
        pass

    @register_service_signal('group_from_multiple_individuals_service.delete')
    def delete(self, obj_data):
        pass
