import graphene
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from core.gql.gql_mutations.base_mutation import BaseHistoryModelDeleteMutationMixin, BaseMutation, \
    BaseHistoryModelUpdateMutationMixin, BaseHistoryModelCreateMutationMixin
from core.schema import OpenIMISMutation
from individual.apps import IndividualConfig
from individual.models import Individual


class CreateIndividualInputType(OpenIMISMutation.Input):
    first_name = graphene.String(required=True, max_length=255)
    last_name = graphene.String(required=True, max_length=255)
    dob = graphene.Date(required=True)

    date_valid_from = graphene.Date(required=False)
    date_valid_to = graphene.Date(required=False)
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

    class Input(OpenIMISMutation.Input):
        uuids = graphene.List(graphene.UUID)
