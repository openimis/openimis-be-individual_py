from datetime import datetime
from django.test import TestCase

from individual.models import Individual, GroupIndividual, Group
from individual.services import GroupIndividualService, CreateGroupAndMoveIndividualService
from individual.tests.data import service_add_individual_payload, service_group_individual_payload

from core.test_helpers import LogInHelper


class CreateGroupAndMoveIndividualServiceTest(TestCase):
    user = None
    service = None
    query_all = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user = LogInHelper().get_or_create_user_api()
        cls.service = CreateGroupAndMoveIndividualService(cls.user)
        cls.query_all = Group.objects.filter(is_deleted=False)
        cls.group = cls.__create_group()
        cls.individual = cls.__create_individual()
        cls.group_individual = cls.__create_group_individual()
        cls.payload = {
            "group_individual_id": cls.group_individual.id,
            "code": 'sickofbadtest'
        }

    def test_create_group_and_move_individual(self):
        test_start_time = datetime.now()
        result = self.service.create(self.payload)
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        uuid = result.get('data', {}).get('uuid', None)
        self.assertEqual(self.query_all.filter(date_created__gte=test_start_time).count(), 1)
        query = self.query_all.filter(uuid=uuid)
        self.assertEqual(query.count(), 1)
        group_individual_id = self.payload.get("group_individual_id")
        self.assertTrue(query.filter(groupindividuals__id=group_individual_id).exists())
        empty_group_query = self.query_all.filter(id=self.group.id)
        self.assertFalse(empty_group_query.filter(groupindividuals__id=group_individual_id).exists())

    @classmethod
    def __create_individual(cls):
        object_data = {
            **service_add_individual_payload
        }

        individual = Individual(**object_data)
        individual.save(username=cls.user.username)

        return individual

    @classmethod
    def __create_group_individual(cls):
        object_data = {
            "group_id": cls.group.id,
            "individual_id": cls.individual.id,
            "role": "HEAD"
        }
        group_individual = GroupIndividual(**object_data)
        group_individual.save(username=cls.user.username)
        return group_individual

    @classmethod
    def __create_group(cls):
        group = Group(code='test-gp')
        group.save(username=cls.user.username)

        return group
