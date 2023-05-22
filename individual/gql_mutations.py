import graphene
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import transaction

from core.gql.gql_mutations.base_mutation import BaseHistoryModelDeleteMutationMixin, BaseMutation, \
    BaseHistoryModelUpdateMutationMixin, BaseHistoryModelCreateMutationMixin
from core.schema import OpenIMISMutation
from individual.apps import IndividualConfig
from individual.models import Individual
from individual.services import IndividualService


class CreateIndividualInputType(OpenIMISMutation.Input):
    first_name = graphene.String(required=True, max_length=255)
    last_name = graphene.String(required=True, max_length=255)
    dob = graphene.Date(required=True)
    json_ext = graphene.types.json.JSONString(required=False)


class UpdateIndividualInputType(CreateIndividualInputType):
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
