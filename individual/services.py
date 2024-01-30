import copy
import logging

from django.db import transaction

from core.models import User
from core.services import BaseService
from core.signals import register_service_signal
from django.utils.translation import gettext as _
from individual.models import Individual, IndividualDataSource, GroupIndividual, Group
from individual.validation import IndividualValidation, IndividualDataSourceValidation, GroupIndividualValidation, \
    GroupValidation
from core.services.utils import check_authentication as check_authentication, output_exception, output_result_success, \
    model_representation
from tasks_management.models import Task
from tasks_management.services import UpdateCheckerLogicServiceMixin, CreateCheckerLogicServiceMixin, \
    crud_business_data_builder

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


class GroupService(BaseService, CreateCheckerLogicServiceMixin):
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
        with transaction.atomic():
            group_id = obj_data.get('id')
            group = Group.objects.filter(id=group_id).first()
            for group_individual in group.groupindividual_set.all():
                # cant use .delete() on query since it will completely remove instances from db instead of marking
                # them as isDeleted
                group_individual.delete(username=self.user.username)
            return super().delete(obj_data)

    @check_authentication
    @register_service_signal('group_service.create_group_individuals')
    def create_group_individuals(self, obj_data):
        try:
            with transaction.atomic():
                self.validation_class.validate_create_group_individuals(self.user, **obj_data)
                individual_ids = obj_data.pop('individual_ids')
                group = self.create(obj_data)
                group_id = group['data']['id']
                service = GroupIndividualService(self.user)
                group_individual_ids = [service.create({'group_id': group_id,
                                                        'individual_id': individual_id})
                                        for individual_id in individual_ids]
                group_and_individuals_message = {**group, 'detail': group_individual_ids}
                return group_and_individuals_message
        except Exception as exc:
            return output_exception(model_name=self.OBJECT_TYPE.__name__, method="create", exception=exc)

    @check_authentication
    @register_service_signal('group_service.update_group_individuals')
    def update_group_individuals(self, obj_data):
        try:
            with transaction.atomic():
                self.validation_class.validate_update_group_individuals(self.user, **obj_data)
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


class CreateGroupAndMoveIndividualService(CreateCheckerLogicServiceMixin):
    OBJECT_TYPE = Group

    def __init__(self, user, validation_class=GroupValidation):
        self.user = user
        self.validation_class = validation_class

    @check_authentication
    @register_service_signal('create_group_and_move_individual.create')
    def create(self, obj_data):
        try:
            with transaction.atomic():
                self.validation_class.validate_create_group_and_move_individual(self.user, **obj_data)
                group_individual_id = obj_data.pop('group_individual_id')
                group = GroupService(self.user).create(obj_data)
                group_individual = GroupIndividual.objects.filter(id=group_individual_id).first()
                group_id = group['data']['id']
                service = GroupIndividualService(self.user)
                service.update({
                    'group_id': group_id, "id": group_individual_id, "role": group_individual.role
                })
                group_and_individuals_message = {**group, 'detail': group_individual_id}
                return group_and_individuals_message
        except Exception as exc:
            return output_exception(model_name=self.OBJECT_TYPE.__name__, method="create", exception=exc)

    def _business_data_serializer(self, data):
        def serialize(key, value):
            if key == 'group_individual_id':
                group_individual = GroupIndividual.objects.get(id=value)
                return f'{group_individual.individual.first_name} {group_individual.individual.last_name}'
            return value

        serialized_data = crud_business_data_builder(data, serialize)
        serialized_data['incoming_data']["id"] = 'NEW_GROUP'
        return serialized_data


class GroupIndividualService(BaseService, UpdateCheckerLogicServiceMixin):
    OBJECT_TYPE = GroupIndividual

    def __init__(self, user, validation_class=GroupIndividualValidation):
        super().__init__(user, validation_class)

    @register_service_signal('groupindividual_service.create')
    def create(self, obj_data):
        return super().create(obj_data)

    @register_service_signal('groupindividual_service.update')
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
                self._handle_json_ext(group_id_before_update, obj_)
                return result
        except Exception as exc:
            return output_exception(model_name=self.OBJECT_TYPE.__name__, method="update", exception=exc)

    @register_service_signal('groupindividual_service.delete')
    def delete(self, obj_data):
        return super().delete(obj_data)

    def _handle_head_change(self, obj_data, obj_):
        with transaction.atomic():
            if obj_.role == GroupIndividual.Role.RECIPIENT and obj_data['role'] == GroupIndividual.Role.HEAD:
                self._change_head(obj_data)

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

    def _handle_json_ext(self, group_id_before_update, obj_):
        self._update_json_ext_for_group(group_id_before_update)
        if group_id_before_update != obj_.group.id:
            self._update_json_ext_for_group(obj_.group.id)

    def _update_json_ext_for_group(self, group_id):
        group = Group.objects.filter(id=group_id).first()
        group_individuals = GroupIndividual.objects.filter(group_id=group_id)
        head = group_individuals.filter(role=GroupIndividual.Role.HEAD).first()

        group_members = {
            str(individual.individual.id): f"{individual.individual.first_name} {individual.individual.last_name}"
            for individual in group_individuals
        }
        head_str = f'{head.individual.first_name} {head.individual.last_name}' if head else None

        changes_to_save = {}

        if group.json_ext.get("members") != group_members:
            changes_to_save["members"] = group_members

        if group.json_ext.get("head") != head_str:
            changes_to_save["head"] = head_str

        if changes_to_save:
            group.json_ext.update(changes_to_save)
            group.save(username=self.user.username)

    def _business_data_serializer(self, data):
        def serialize(key, value):
            if key == 'id':
                group_individual = GroupIndividual.objects.get(id=value)
                return f'{group_individual.individual.first_name} {group_individual.individual.last_name}'
            return value

        serialized_data = crud_business_data_builder(data, serialize)
        return serialized_data



def group_on_task_complete_service_handler(service_type):
    operations = []
    if issubclass(service_type, CreateCheckerLogicServiceMixin):
        operations.append('create')

    def func(**kwargs):
        try:
            result = kwargs.get('result', {})
            task = result['data']['task']
            business_event = task['business_event']
            service_match = business_event.startswith(f"{service_type.__name__}.")
            if result and result['success'] \
                    and task['status'] == Task.Status.COMPLETED \
                    and service_match:
                operation = business_event.split(".")[1]
                if operation in operations:
                    user = User.objects.get(id=result['data']['user']['id'])
                    data = task['data']['incoming_data']
                    getattr(service_type(user), operation)(data)
        except Exception as e:
            logger.error("Error while executing on_task_complete", exc_info=e)
            return [str(e)]

    return func

