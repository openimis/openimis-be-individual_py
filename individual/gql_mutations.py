import graphene
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import transaction

from core.gql.gql_mutations.base_mutation import BaseHistoryModelDeleteMutationMixin, BaseMutation, \
    BaseHistoryModelUpdateMutationMixin, BaseHistoryModelCreateMutationMixin
from core.schema import OpenIMISMutation
from individual.apps import IndividualConfig
from individual.models import Individual, Group, GroupIndividual
from individual.services import IndividualService, GroupService, GroupIndividualService


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


class CreateIndividualMutation(BaseHistoryModelCreateMutationMixin, BaseMutation):
    _mutation_class = "CreateIndividualMutation"
    _mutation_module = "individual"
    _model = Individual

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                IndividualConfig.gql_individual_create_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = IndividualService(user)
        service.create(data)

    class Input(CreateIndividualInputType):
        pass


class UpdateIndividualMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdateIndividualMutation"
    _mutation_module = "individual"
    _model = Individual

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                IndividualConfig.gql_individual_update_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "date_valid_to" not in data:
            data['date_valid_to'] = None
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = IndividualService(user)
        service.update(data)

    class Input(UpdateIndividualInputType):
        pass


class DeleteIndividualMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeleteIndividualMutation"
    _mutation_module = "individual"
    _model = Individual

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
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
        if type(user) is AnonymousUser or not user.has_perms(
                IndividualConfig.gql_group_create_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupService(user)
        service.create(data)

    class Input(CreateGroupInputType):
        pass


class UpdateGroupMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdateGroupMutation"
    _mutation_module = "individual"
    _model = Group

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if type(user) is AnonymousUser or not user.has_perms(
                IndividualConfig.gql_group_update_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "date_valid_to" not in data:
            data['date_valid_to'] = None
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupService(user)
        service.update(data)

    class Input(UpdateGroupInputType):
        pass


class DeleteGroupMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeleteGroupMutation"
    _mutation_module = "social_protection"
    _model = Group

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
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
        if type(user) is AnonymousUser or not user.has_perms(
                IndividualConfig.gql_group_create_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupIndividualService(user)
        service.create(data)

    class Input(CreateGroupIndividualInputType):
        pass


class UpdateGroupIndividualMutation(BaseHistoryModelUpdateMutationMixin, BaseMutation):
    _mutation_class = "UpdateGroupIndividualMutation"
    _mutation_module = "individual"
    _model = GroupIndividual

    @classmethod
    def _validate_mutation(cls, user, **data):
        super()._validate_mutation(user, **data)
        if type(user) is AnonymousUser or not user.has_perms(
                IndividualConfig.gql_group_update_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "date_valid_to" not in data:
            data['date_valid_to'] = None
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupIndividualService(user)
        service.update(data)

    class Input(UpdateGroupIndividualInputType):
        pass


class DeleteGroupIndividualMutation(BaseHistoryModelDeleteMutationMixin, BaseMutation):
    _mutation_class = "DeleteGroupIndividualMutation"
    _mutation_module = "individual"
    _model = GroupIndividual

    @classmethod
    def _validate_mutation(cls, user, **data):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
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
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                IndividualConfig.gql_group_create_perms):
            raise ValidationError("mutation.authentication_required")

    @classmethod
    def _mutate(cls, user, **data):
        if "client_mutation_id" in data:
            data.pop('client_mutation_id')
        if "client_mutation_label" in data:
            data.pop('client_mutation_label')

        service = GroupService(user)
        service.create_group_individuals(data)

    class Input(CreateGroupInputType):
        individual_ids = graphene.List(graphene.UUID)
