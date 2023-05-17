import graphene
from graphene_django import DjangoObjectType

from core import ExtendedConnection
from individual.models import Individual


class IndividualGQLType(DjangoObjectType):
    uuid = graphene.String(source='uuid')

    class Meta:
        model = Individual
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "first_name": ["exact"],
            "last_name": ["exact"],
            "dob": ["exact", "lt", "lte", "gt", "gte"],

            "date_created": ["exact", "lt", "lte", "gt", "gte"],
            "date_updated": ["exact", "lt", "lte", "gt", "gte"],
            "is_deleted": ["exact"],
            "version": ["exact"],
        }
        connection_class = ExtendedConnection
