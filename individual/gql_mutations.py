import graphene
from django.core.exceptions import ValidationError
from django.db import transaction

from core.gql.gql_mutations.base_mutation import BaseHistoryModelDeleteMutationMixin, BaseMutation, \
    BaseHistoryModelUpdateMutationMixin, BaseHistoryModelCreateMutationMixin
from core.schema import OpenIMISMutation
from individual.apps import IndividualConfig
from individual.models import Individual, Group, GroupIndividual
from individual.services import IndividualService, GroupService, GroupIndividualService, \
    CreateGroupAndMoveIndividualService
from individual.tasks import (
    task_import_individual_workflow,
    task_import_individual_workflow_valid
)


class CreateIndividualInputType(OpenIMISMutation.Input):
    first_name = graphene.String(required=True, max_length=255)
    last_name = graphene.String(required=True, max_length=255)
    dob = graphene.Date(required=True)
    json_ext = graphene.types.json.JSONString(required=False)


class UpdateIndividualInputType(CreateIndividualInputType):
    id = graphene.UUID(required=True)


class CreateGroupInputType(OpenIMISMutation.Input):
    pass


class UpdateGroupInputType(CreateGroupInputType):
    id = graphene.UUID(required=True)


class CreateGroupIndividualInputType(OpenIMISMutation.Input):
    class RoleEnum(graphene.Enum):
        HEAD = GroupIndividual.Role.HEAD
        RECIPIENT = GroupIndividual.Role.RECIPIENT

    group_id = graphene.UUID(required=True)
    individual_id = graphene.UUID(required=True)
    role = graphene.Field(RoleEnum, required=False)

    def resolve_role(self, info):
        return self.role


class UpdateGroupIndividualInputType(CreateGroupIndividualInputType):
    id = graphene.UUID(required=True)


class ConfirmIndividualEnrollmentInputType(OpenIMISMutation.Input):
    custom_filters = graphene.List(required=False, of_type=graphene.String)
    benefit_plan_id = graphene.String(required=True, max_lenght=255)
    status = graphene.String(required=True, max_lenght=255)


class CreateIndividualMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreateIndividualMutation"
    _mutation_module = "individual"
    _model = Individual

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_individual_create_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = IndividualService(user)
        result = service.create(data)
        return result if not result['success'] else None

    class Input(CreateIndividualInputType):
        pass


class UpdateIndividualMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdateIndividualMutation"
    _mutation_module = "individual"
    _model = Individual

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_individual_update_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = IndividualService(user)
        if IndividualConfig.check_individual_update:
            result = service.create_update_task(data)
        else:
            result = service.update(data)
        return result if not result['success'] else None

    class Input(UpdateIndividualInputType):
        pass


class DeleteIndividualMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeleteIndividualMutation"
    _mutation_module = "individual"
    _model = Individual

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_individual_delete_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = IndividualService(user)

        ids = data.get('ids')
        if ids:
            with transaction.atomic():
                for id in ids:
                    service.delete({'id': id})

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


class CreateGroupMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreateGroupMutation"
    _mutation_module = "individual"
    _model = Group

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_group_create_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupService(user)
        result = service.create(data)
        return result if not result['success'] else None

    class Input(CreateGroupInputType):
        pass


class UpdateGroupMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdateGroupMutation"
    _mutation_module = "individual"
    _model = Group

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_group_update_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupService(user)
        result = service.update(data)
        return result if not result['success'] else None

    class Input(UpdateGroupInputType):
        pass


class DeleteGroupMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeleteGroupMutation"
    _mutation_module = "social_protection"
    _model = Group

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_group_delete_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupService(user)

        ids = data.get('ids')
        if ids:
            with transaction.atomic():
                for id in ids:
                    service.delete({'id': id})

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


class CreateGroupIndividualMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreateGroupIndividualMutation"
    _mutation_module = "individual"
    _model = GroupIndividual

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_group_create_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupIndividualService(user)
        result = service.create(data)
        return result if not result['success'] else None

    class Input(CreateGroupIndividualInputType):
        pass


class UpdateGroupIndividualMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdateGroupIndividualMutation"
    _mutation_module = "individual"
    _model = GroupIndividual

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_group_update_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupIndividualService(user)
        if IndividualConfig.check_group_individual_update:
            result = service.create_update_task(data)
        else:
            result = service.update(data)
        return result if not result['success'] else None

    class Input(UpdateGroupIndividualInputType):
        pass


class DeleteGroupIndividualMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeleteGroupIndividualMutation"
    _mutation_module = "individual"
    _model = GroupIndividual

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_group_delete_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupIndividualService(user)

        ids = data.get('ids')
        if ids:
            with transaction.atomic():
                for id in ids:
                    service.delete({'id': id})

    class Input(OpenIMISMutation.Input):
        ids = graphene.List(graphene.UUID)


class CreateGroupIndividualsMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreateGroupIndividualsMutation"
    _mutation_module = "individual"
    _model = Group

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_group_create_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupService(user)
        result = service.create_group_individuals(data)
        return result if not result['success'] else None

    class Input(CreateGroupInputType):
        individual_ids = graphene.List(graphene.UUID, required=True)


class CreateGroupAndMoveIndividualMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreateGroupAndMoveIndividualMutation"
    _mutation_module = "individual"
    _model = Group

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)

        required_perms = IndividualConfig.gql_group_create_perms + IndividualConfig.gql_group_update_perms
        if not user.has_perms(required_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = CreateGroupAndMoveIndividualService(user)
        if IndividualConfig.check_group_individual_update or IndividualConfig.check_group_create:
            result = service.create_create_task(data)
        else:
            result = service.create(data)
        return result if not result['success'] else None

    class Input(CreateGroupInputType):
        group_individual_id = graphene.UUID(required=True)


class ConfirmIndividualEnrollmentMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "ConfirmIndividualEnrollmentMutation"
    _mutation_module = "individual"
    _model = Individual

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if not user.has_perms(
                IndividualConfig.gql_group_create_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')
        custom_filters = data.pop('custom_filters', None)
        benefit_plan_id = data.pop('benefit_plan_id', None)
        status = data.pop('status', "ACTIVE")
        service = IndividualService(user)
        service.select_individuals_to_benefit_plan(
            custom_filters,
            benefit_plan_id,
            status,
            user,
        )
        return None

    class Input(ConfirmIndividualEnrollmentInputType):
        pass
