import copy

from django.test import TestCase

from individual.models import Group, Individual, GroupIndividual
from individual.services import GroupFromMultipleIndividualsService
from individual.tests.data import service_add_individual_payload
from individual.tests.helpers import LogInHelper


class GroupFromMultipleIndividualsServiceTest(TestCase):
    user = None
    service = None
    query_all = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user = LogInHelper().get_or_create_user_api()
        cls.service = GroupFromMultipleIndividualsService(cls.user)
        cls.query_all = Group.objects.filter(is_deleted=False)
        cls.group_individual_query_all = GroupIndividual.objects.filter(is_deleted=False)
        cls.individual1 = cls.__create_individual()
        cls.individual2 = cls.__create_individual()
        cls.payload = {
            'individual_ids': [cls.individual1.id, cls.individual2.id]
        }

    def test_add_group_with_multiple_individuals(self):
        result = self.service.create(self.payload)
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        uuid = result.get('data', {}).get('uuid', None)
        query = self.query_all.filter(uuid=uuid)
        group = query.first()
        self.assertEqual(query.count(), 1)
        group_individual_query = self.group_individual_query_all.filter(group=group)
        self.assertEqual(group_individual_query.count(), 2)

    @classmethod
    def __create_individual(cls):
        object_data = {
            **service_add_individual_payload
        }

        individual = Individual(**object_data)
        individual.save(username=cls.user.username)

        return individual

