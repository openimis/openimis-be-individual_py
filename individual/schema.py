import graphene
from django.contrib.auth.models import AnonymousUser
from django.db.models import Q

from core.schema import OrderedDjangoFilterConnectionField
from core.utils import append_validity_filter
from individual.apps import IndividualConfig
from individual.gql_mutations import CreateIndividualMutation, UpdateIndividualMutation, DeleteIndividualMutation
from individual.gql_queries import IndividualGQLType, IndividualDataSourceGQLType
from individual.models import Individual, IndividualDataSource
import graphene_django_optimizer as gql_optimizer


class Query:
    individual = OrderedDjangoFilterConnectionField(
        IndividualGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String()
    )

    individual_data_source = OrderedDjangoFilterConnectionField(
        IndividualDataSourceGQLType,
        orderBy=graphene.List(of_type=graphene.String),
        applyDefaultValidityFilter=graphene.Boolean(),
        client_mutation_id=graphene.String()
    )

    def resolve_individual(self, info, **kwargs):
        filters = append_validity_filter(**kwargs)

        client_mutation_id = kwargs.get("client_mutation_id")
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        Query._check_permissions(info.context.user)
        query = Individual.objects.filter(*filters)
        return gql_optimizer.query(query, info)

    def resolve_individual_data_source(self, info, **kwargs):
        filters = append_validity_filter(**kwargs)

        client_mutation_id = kwargs.get("client_mutation_id")
        if client_mutation_id:
            filters.append(Q(mutations__mutation__client_mutation_id=client_mutation_id))

        Query._check_permissions(info.context.user)
        query = IndividualDataSource.objects.filter(*filters)
        return gql_optimizer.query(query, info)

    @staticmethod
    def _check_permissions(user):
        if type(user) is AnonymousUser or not user.id or not user.has_perms(
                IndividualConfig.gql_individual_search_perms):
            raise PermissionError("Unauthorized")


class Mutation(graphene.ObjectType):
    create_individual = CreateIndividualMutation.Field()
    update_individual = UpdateIndividualMutation.Field()
    delete_individual = DeleteIndividualMutation.Field()
