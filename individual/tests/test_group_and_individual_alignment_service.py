from unittest import mock

from django.test import TestCase

from core.test_helpers import LogInHelper
from individual.apps import IndividualConfig
from individual.models import Individual, GroupIndividual, Group
from individual.services import GroupAndGroupIndividualAlignmentService
from individual.tests.test_helpers import (
    add_individual_to_group,
    create_individual,
    create_group,
)
from location.test_helpers import create_test_village


class GroupAndGroupIndividualAlignmentServiceTest(TestCase):
    user = None
    service = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user = LogInHelper().get_or_create_user_api()
        cls.username = cls.user.username
        cls.service = GroupAndGroupIndividualAlignmentService(cls.user)

        cls.loc_a = create_test_village({
            'name': 'Village A',
            'code': 'ViaA',
        })

        cls.loc_b = create_test_village({
            'name': 'Village B',
            'code': 'ViaB'
        })

    def setUp(self):
        self.group = create_group(self.username)
        self.individual = create_individual(self.username)

    def assert_group_and_individual_location_equal(self, group_id, individual_id, location_id):
        group = Group.objects.get(id=group_id)
        individual = Individual.objects.get(id=individual_id)
        self.assertEqual(group.location_id, location_id)
        self.assertEqual(individual.location_id, location_id)

    def test_ensure_location_consistent_for_head(self):
        role = GroupIndividual.Role.HEAD

        # When group loc = head loc = None, no op
        self.service.ensure_location_consistent(self.group, self.individual, role)
        self.assert_group_and_individual_location_equal(
            self.group.id, self.individual.id, None
        )

        # When group has no loc, head has loc, group takes location of the head
        self.individual.location = self.loc_a
        self.individual.save(user=self.user)
        self.service.ensure_location_consistent(self.group, self.individual, role)
        self.assert_group_and_individual_location_equal(
            self.group.id, self.individual.id, self.loc_a.id
        )

        # When head has no loc, group has loc, head takes location of the group
        self.individual.location = None
        self.individual.save(user=self.user)
        self.group.location = self.loc_b
        self.group.save(user=self.user)
        self.service.ensure_location_consistent(self.group, self.individual, role)
        self.assert_group_and_individual_location_equal(
            self.group.id, self.individual.id, self.loc_b.id
        )

        # When group and head have diff loc, update head to use group loc
        self.individual.location = self.loc_a
        self.individual.save(user=self.user)
        self.service.ensure_location_consistent(self.group, self.individual, role)
        self.assert_group_and_individual_location_equal(
            self.group.id, self.individual.id, self.loc_b.id
        )

    def test_ensure_location_consistent_for_non_head(self):
        role = None

        # When group loc = non-head loc = None, no op
        self.service.ensure_location_consistent(self.group, self.individual, role)
        self.assert_group_and_individual_location_equal(
            self.group.id, self.individual.id, None
        )

        # When the group has no loc yet, the non-head keeps its own - it cannot give the
        # group a location, and blanking its own would only destroy valid data
        self.individual.location = self.loc_a
        self.individual.save(user=self.user)
        self.service.ensure_location_consistent(self.group, self.individual, role)
        self.assertIsNone(Group.objects.get(id=self.group.id).location_id)
        self.assertEqual(Individual.objects.get(id=self.individual.id).location_id, self.loc_a.id)

        # Once the group has a loc, individual loc takes group loc
        self.group.location = self.loc_b
        self.group.save(user=self.user)
        self.service.ensure_location_consistent(self.group, self.individual, role)
        self.assert_group_and_individual_location_equal(
            self.group.id, self.individual.id, self.loc_b.id
        )

    def test_member_joining_household_without_head_keeps_its_location(self):
        # The path a bulk import takes: members are added to a group whose head has not
        # been (or never will be) added, e.g. because the head's record was rejected.
        self.individual.location = self.loc_a
        self.individual.save(user=self.user)

        add_individual_to_group(self.username, self.individual, self.group, is_head=False)

        self.assertEqual(Individual.objects.get(id=self.individual.id).location_id, self.loc_a.id,
                         "a member of a household with no location lost its own location")


class GroupJsonExtFromHeadTest(TestCase):
    # Keys a household carries but its head does not, as a group upload writes them.
    household_keys = {'household_size': 5, 'household_type': 'RURAL'}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        cls.username = cls.user.username

    def setUp(self):
        self.head = create_individual(self.username, {'json_ext': {'head_only': 'from-head'}})
        self.group = create_group(self.username)
        add_individual_to_group(self.username, self.head, self.group, is_head=True)
        self.group.refresh_from_db()
        self.group.json_ext.update(self.household_keys)
        self.group.save(username=self.username)

    def add_member(self):
        member = create_individual(self.username, {'first_name': 'Member'})
        add_individual_to_group(self.username, member, self.group, is_head=False)

    def group_json_ext(self):
        self.group.refresh_from_db()
        return self.group.json_ext

    def test_keys_the_head_lacks_are_kept(self):
        self.add_member()

        json_ext = self.group_json_ext()
        self.assertEqual(len(json_ext['members']), 2)
        for key, value in self.household_keys.items():
            self.assertEqual(json_ext.get(key), value, key)

    def test_head_values_are_copied(self):
        self.head.json_ext = {**self.head.json_ext, 'head_only': 'updated', 'household_size': 6}
        self.head.save(username=self.username)
        self.add_member()

        json_ext = self.group_json_ext()
        self.assertEqual(json_ext['head_only'], 'updated')
        self.assertEqual(json_ext['household_size'], 6)
        self.assertEqual(json_ext['household_type'], 'RURAL')

    def test_head_value_set_to_none_clears_the_group_value(self):
        self.head.json_ext = {**self.head.json_ext, 'household_type': None}
        self.head.save(username=self.username)
        self.add_member()

        json_ext = self.group_json_ext()
        self.assertNotIn('household_type', json_ext)
        self.assertEqual(json_ext['household_size'], 5)

    def test_configured_keys_keep_the_group_value(self):
        self.head.json_ext = {**self.head.json_ext, 'household_size': 6, 'household_type': None}
        self.head.save(username=self.username)
        with mock.patch.object(
            IndividualConfig, 'group_json_ext_keys_not_copied_from_head',
            ['household_size', 'household_type'], create=True,
        ):
            self.add_member()

        json_ext = self.group_json_ext()
        self.assertEqual(json_ext['household_size'], 5)
        self.assertEqual(json_ext['household_type'], 'RURAL')
