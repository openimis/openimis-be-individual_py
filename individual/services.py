import logging

from django.db import transaction

from core.services import BaseService
from core.signals import register_service_signal
from django.utils.translation import gettext as _
from individual.models import Individual, IndividualDataSource, GroupIndividual, Group
from individual.validation import IndividualValidation, IndividualDataSourceValidation, GroupIndividualValidation, \
    GroupValidation
from core.services.utils import check_authentication as check_authentication, output_exception, output_result_success, \
    model_representation
from tasks_management.services import UpdateCheckerLogicServiceMixin

logger = logging.getLogger(__name__)


class IndividualService(BaseService, UpdateCheckerLogicServiceMixin):
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


class GroupIndividualService(BaseService, UpdateCheckerLogicServiceMixin):
    OBJECT_TYPE = GroupIndividual

    def __init__(self, user, validation_class=GroupIndividualValidation):
        super().__init__(user, validation_class)

    @register_service_signal('group_individual_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('group_individual.update')
    @check_authentication
    def update(self, obj_data):
        try:
            with transaction.atomic():
                obj_data = self._adjust_update_payload(obj_data)
                self.validation_class.validate_update(self.user, **obj_data)
                obj_ = self.OBJECT_TYPE.objects.filter(id=obj_data['id']).first()
                group_id_before_update = obj_.group.id
                self._handle_head_change(obj_data, obj_)
                [setattr(obj_, key, obj_data[key]) for key in obj_data]
                result = self.save_instance(obj_)
                self._handle_members_change(group_id_before_update, obj_)
                return result
        except Exception as exc:
            return output_exception(model_name=self.OBJECT_TYPE.__name__, method="update", exception=exc)

    def _handle_head_change(self, obj_data, obj_):
        with transaction.atomic():
            if obj_.role == GroupIndividual.Role.RECIPIENT and obj_data['role'] == GroupIndividual.Role.HEAD:
                self._change_head(obj_data)
                self._update_group_json_ext(obj_)

    def _handle_members_change(self, group_id_before_update, obj_):

        with transaction.atomic():
            new_group = Group.objects.filter(id=group_id_before_update).first()
            new_group_individuals = GroupIndividual.objects.filter(group_id=group_id_before_update)

            new_group_members = {
                str(individual.individual.id): f"{individual.individual.first_name} {individual.individual.last_name}"
                for individual in new_group_individuals
            }

            new_group.json_ext["members"] = new_group_members
            new_group.save(username=self.user.username)

            if group_id_before_update != obj_.group.id:
                old_group = Group.objects.filter(id=obj_.group.id).first()
                old_group_individuals = GroupIndividual.objects.filter(group_id=obj_.group.id)

                old_group_members = {
                    str(individual.individual.id): f"{individual.individual.first_name} {individual.individual.last_name}"
                    for individual in old_group_individuals
                }

                old_group.json_ext["members"] = old_group_members
                old_group.save(username=self.user.username)

    def _change_head(self, obj_data):
        with transaction.atomic():
            group_id = obj_data.get('group_id')
            group_queryset = GroupIndividual.objects.filter(group_id=group_id, role=GroupIndividual.Role.HEAD)
            old_head = group_queryset.first()
            if old_head:
                old_head.role = GroupIndividual.Role.RECIPIENT
                old_head.save(username=self.user.username)

            if group_queryset.exists():
                raise ValueError(_("more_than_one_head_in_group"))

    def _update_group_json_ext(self, obj_):
        with transaction.atomic():
            group = Group.objects.filter(groupindividual=obj_).first()
            if group:
                group.json_ext['head'] = f'{obj_.individual.first_name} {obj_.individual.last_name}'
                group.save(username=self.user.username)

    @register_service_signal('group_individual.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)

    def _data_for_json_ext_update(self, obj_data):
        group_individual = GroupIndividual.objects.get(id=obj_data.get("id"))
        individual = group_individual.individual
        individual_identity_string = f'{individual.first_name} {individual.last_name}'
        json_ext_data = {"individual_identity": individual_identity_string}
        return json_ext_data
