from django.test import TestCase

from core.test_helpers import LogInHelper
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

        # Otherwise individual loc takes group loc
        self.individual.location = self.loc_a
        self.individual.save(user=self.user)
        self.service.ensure_location_consistent(self.group, self.individual, role)
        self.assert_group_and_individual_location_equal(
            self.group.id, self.individual.id, None
        )

        self.group.location = self.loc_b
        self.group.save(user=self.user)
        self.service.ensure_location_consistent(self.group, self.individual, role)
        self.assert_group_and_individual_location_equal(
            self.group.id, self.individual.id, self.loc_b.id
        )


class GroupJsonExtAlignmentTest(TestCase):
    household_keys = {'household_size': 5, 'is_refugee_household': False, 'household_type': 'RURAL'}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        cls.username = cls.user.username

    def setUp(self):
        self.head = create_individual(
            self.username, {'first_name': 'Head', 'json_ext': {'head_only': 'from-head'}}
        )
        self.group = create_group(self.username)
        self.head_link = add_individual_to_group(self.username, self.head, self.group, is_head=True)
        self.group.refresh_from_db()
        self.group.json_ext.update(self.household_keys)
        self.group.save(username=self.username)

    def _refreshed_json_ext(self):
        self.group.refresh_from_db()
        return self.group.json_ext

    def assert_household_keys_kept(self, json_ext):
        for key, value in self.household_keys.items():
            self.assertIn(key, json_ext)
            self.assertEqual(json_ext[key], value)

    def test_household_keys_kept_when_member_added(self):
        member = create_individual(self.username, {'first_name': 'Member'})
        add_individual_to_group(self.username, member, self.group, is_head=False)

        json_ext = self._refreshed_json_ext()
        self.assertIn(str(member.id), json_ext['members'])
        self.assertEqual(len(json_ext['members']), 2)
        self.assert_household_keys_kept(json_ext)

    def test_household_keys_kept_when_member_removed(self):
        member = create_individual(self.username, {'first_name': 'Member'})
        member_link = add_individual_to_group(self.username, member, self.group, is_head=False)
        member_link.delete(username=self.username)

        json_ext = self._refreshed_json_ext()
        self.assertNotIn(str(member.id), json_ext['members'])
        self.assert_household_keys_kept(json_ext)

    def test_household_keys_kept_when_primary_recipient_changes(self):
        self.head_link.recipient_type = GroupIndividual.RecipientType.PRIMARY
        self.head_link.save(username=self.username)
        self.assertEqual(self._refreshed_json_ext()['primary_recipient_id'], str(self.head.id))

        member = create_individual(self.username, {'first_name': 'Member'})
        member_link = add_individual_to_group(self.username, member, self.group, is_head=False)
        member_link.recipient_type = GroupIndividual.RecipientType.PRIMARY
        member_link.save(username=self.username)

        json_ext = self._refreshed_json_ext()
        self.assertEqual(json_ext['primary_recipient_id'], str(member.id))
        self.assert_household_keys_kept(json_ext)

    def test_head_json_ext_keys_copied_to_group(self):
        self.assertEqual(self._refreshed_json_ext()['head_only'], 'from-head')

        self.head.json_ext = {
            **self.head.json_ext, 'head_only': 'updated', 'head_new': 1, 'household_type': None
        }
        self.head.save(username=self.username)
        member = create_individual(self.username, {'first_name': 'Member'})
        add_individual_to_group(self.username, member, self.group, is_head=False)

        json_ext = self._refreshed_json_ext()
        self.assertEqual(json_ext['head_only'], 'updated')
        self.assertEqual(json_ext['head_new'], 1)
        self.assertEqual(json_ext['head_id'], str(self.head.id))
        self.assert_household_keys_kept(json_ext)
