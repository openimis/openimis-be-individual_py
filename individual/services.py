import logging

from django.db import transaction

from core.services import BaseService
from core.signals import register_service_signal
from individual.models import Individual, IndividualDataSource, GroupIndividual, Group
from individual.validation import IndividualValidation, IndividualDataSourceValidation, GroupIndividualValidation, \
    GroupValidation
from core.services.utils import check_authentication as check_authentication, output_exception, output_result_success, \
    model_representation

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

    @check_authentication
    @register_service_signal('group_service.create_group_individuals')
    def create_group_individuals(self, obj_data):
        try:
            with transaction.atomic():
                individual_ids = obj_data.pop('individual_ids')
                group = self.create(obj_data)
                group_id = group['data']['id']
                service = GroupIndividualService(self.user)
                individual_ids_list = [service.create({'group_id': group_id,
                                                       'individual_id': individual_id})
                                       for individual_id in individual_ids]
                group_and_individuals_message = {**group, 'detail': individual_ids_list}
                return group_and_individuals_message
        except Exception as exc:
            return output_exception(model_name=self.OBJECT_TYPE.__name__, method="create", exception=exc)

    @check_authentication
    @register_service_signal('group_service.update_group_individuals')
    def update_group_individuals(self, obj_data):
        try:
            with transaction.atomic():
                self.validation_class.validate_update(self.user, **obj_data)
                individual_ids = obj_data.pop('individual_ids')
                group_id = obj_data.pop('id')
                obj_ = self.OBJECT_TYPE.objects.filter(id=group_id).first()
                obj_.groupindividual_set.all().delete()
                service = GroupIndividualService(self.user)

                individual_ids_list = [service.create({'group_id': group_id,
                                                       'individual_id': individual_id})
                                       for individual_id in individual_ids]
                group_dict_repr = model_representation(obj_)
                result_message = output_result_success(group_dict_repr)
                group_and_individuals_message = {**result_message, 'detail': individual_ids_list}
                return group_and_individuals_message
        except Exception as exc:
            return output_exception(model_name=self.OBJECT_TYPE.__name__, method="update", exception=exc)


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
