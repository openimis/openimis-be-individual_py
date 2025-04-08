import json
from individual.tests.test_helpers import (
    create_group,
    create_individual,
    create_group_with_individual,
    IndividualGQLTestCase,
)
from individual.models import GroupIndividual, Group
from tasks_management.models import Task
from unittest.mock import patch
from individual.apps import IndividualConfig
from django.utils.translation import gettext as _
from django.contrib.contenttypes.models import ContentType


class GroupGQLMutationTest(IndividualGQLTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_create_group_general_permission(self):
        query_str = f'''
            mutation {{
              createGroup(
                input: {{
                  code: "GF"
                  individualsData: []
                  locationId: {self.village_a.id}
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # Anonymous User has no permission
        response = self.query(query_str)

        content = json.loads(response.content)
        internal_id = content['data']['createGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['createGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['createGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized'))

    def test_create_group_row_security(self):
        query_str = f'''
            mutation {{
              createGroup(
                input: {{
                  code: "GBVA"
                  individualsData: []
                  locationId: {self.village_a.id}
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot create group for district A
        response = self.query(query_str)
        content = json.loads(response.content)
        internal_id = content['data']['createGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))
        
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        internal_id = content['data']['createGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized.location'))

        # SP officer A can create group for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['createGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # SP officer B can create group for district B
        response = self.query(
            query_str.replace(
                f'locationId: {self.village_a.id}',
                f'locationId: {self.village_b.id}'
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['createGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # SP officer B can create group without any district
        response = self.query(
            query_str.replace(f'locationId: {self.village_a.id}', ' '),
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['createGroup']['internalId']
        self.assert_mutation_success(internal_id)

    def test_update_group_general_permission(self):
        group = create_group(self.admin_user.username)
        query_str = f'''
            mutation {{
              updateGroup(
                input: {{
                  id: "{group.id}"
                  locationId: {self.village_a.id}
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        self.assertResponseNoErrors(response)
        content = json.loads(response.content)
        internal_id = content['data']['updateGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # Anonymous User has no permission
        response = self.query(query_str)
        content = json.loads(response.content)
        internal_id = content['data']['updateGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['updateGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized'))

    def test_update_group_row_security(self):
        group_a = create_group(
            self.admin_user.username,
            payload_override={'location': self.village_a},
        )
        query_str = f'''
            mutation {{
              updateGroup(
                input: {{
                  id: "{group_a.id}"
                  code: "GBAR"
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot update group for district A
        response = self.query(query_str)
        content = json.loads(response.content)
        internal_id = content['data']['updateGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        internal_id = content['data']['updateGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized.location'))

        # SP officer A can update group for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['updateGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # SP officer B can update group without any district
        group_no_loc = create_group(self.admin_user.username)
        response = self.query(
            query_str.replace(
                f'id: "{group_a.id}"',
                f'id: "{group_no_loc.id}"'
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['updateGroup']['internalId']
        self.assert_mutation_success(internal_id)

    @patch.object(IndividualConfig, 'check_group_delete', False)
    def test_delete_group_general_permission(self):
        group1 = create_group(
            self.admin_user.username,
            payload_override={'location': self.village_a},
        )
        group2 = create_group(
            self.admin_user.username,
            payload_override={'location': self.village_b},
        )
        query_str = f'''
            mutation {{
              deleteGroup(
                input: {{
                  ids: ["{group1.id}", "{group2.id}"]
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # Anonymous User has no permission
        response = self.query(query_str)

        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized'))

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_success(internal_id)

    @patch.object(IndividualConfig, 'check_group_delete', False)
    def test_delete_group_row_security(self):
        group_a1 = create_group(
            self.admin_user.username,
            payload_override={'location': self.village_a},
        )
        group_a2 = create_group(
            self.admin_user.username,
            payload_override={'location': self.village_a},
        )
        group_b = create_group(
            self.admin_user.username,
            payload_override={'location': self.village_b},
        )
        query_str = f'''
            mutation {{
              deleteGroup(
                input: {{
                  ids: ["{group_a1.id}"]
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot delete group for district A
        response = self.query(query_str)
        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized.location'))

        # SP officer A can delete group for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # SP officer B can delete group without any district
        group_no_loc = create_group(self.admin_user.username)
        response = self.query(
            query_str.replace(
                str(group_a1.id),
                str(group_no_loc.id)
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # SP officer B cannot delete a mix of groups from district A and district B
        response = self.query(
            query_str.replace(
                f'["{group_a1.id}"]',
                f'["{group_a1.id}", "{group_b.id}"]'
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized.location'))

        # SP officer B can delete group from district B
        group_no_loc = create_group(self.admin_user.username)
        response = self.query(
            query_str.replace(
                str(group_a1.id),
                str(group_b.id)
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_success(internal_id)

    @patch.object(IndividualConfig, 'check_group_delete', True)
    def test_delete_group_with_check(self):
        group = create_group(self.admin_user.username)
        query_str = f'''
                mutation {{
                  deleteGroup(
                    input: {{
                      ids: ["{group.id}"]
                    }}
                  ) {{
                    clientMutationId
                    internalId
                  }}
                }}
            '''

        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['deleteGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # Check that the group is not yet deleted
        group_query = Group.objects.filter(
            is_deleted=False,
            id=group.id,
        )
        self.assertEqual(group_query.count(), 1)

        # Check that a group delete task is created
        task_query = Task.objects.filter(
            entity_type=ContentType.objects.get_for_model(Group),
            entity_id=group.id,
            business_event='GroupService.delete',
        )
        self.assertEqual(task_query.count(), 1)


    def test_add_individual_to_group_general_permission(self):
        group = create_group(self.admin_user.username)
        individual = create_individual(self.admin_user.username)
        query_str = f'''
            mutation {{
              addIndividualToGroup(
                input: {{
                  groupId: "{group.id}"
                  individualId: "{individual.id}"
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # Anonymous User has no permission
        response = self.query(query_str)

        content = json.loads(response.content)
        internal_id = content['data']['addIndividualToGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['addIndividualToGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized'))

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['addIndividualToGroup']['internalId']
        self.assert_mutation_success(internal_id)

    def test_add_individual_to_group_row_security(self):
        group_a = create_group(
            self.admin_user.username,
            payload_override={'location': self.village_a},
        )
        group_b = create_group(
            self.admin_user.username,
            payload_override={'location': self.village_b},
        )
        group_no_loc = create_group(self.admin_user.username)

        individual_a = create_individual(
            self.admin_user.username,
            payload_override={'location': self.village_a},
        )
        individual_b = create_individual(
            self.admin_user.username,
            payload_override={'location': self.village_b},
        )
        individual_no_loc = create_individual(self.admin_user.username)

        query_str = f'''
            mutation {{
              addIndividualToGroup(
                input: {{
                  groupId: "{group_a.id}"
                  individualId: "{individual_a.id}"
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot add individual to group for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['addIndividualToGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized.location'))

        # SP officer B can add individual to group for district B
        query_str_b = query_str.replace(
            str(individual_a.id), str(individual_b.id)
        ).replace(
            str(group_a.id), str(group_b.id)
        )
        response = self.query(
            query_str_b,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['addIndividualToGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # SP officer A can add individual to group for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['addIndividualToGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # SP officer A can add individual without location to group in district A
        response = self.query(
            query_str.replace(str(individual_a.id), str(individual_no_loc.id)),
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['addIndividualToGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # Adding a individual to a group with different locations is not allowed
        response = self.query(
            query_str.replace(str(group_a.id), str(group_b.id)),
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['addIndividualToGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.individual_group_location_mismatch'))

        # SP officer A can add individual from district A to group without location
        response = self.query(
            query_str.replace(str(group_a.id), str(group_no_loc.id)),
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['addIndividualToGroup']['internalId']
        self.assert_mutation_success(internal_id)

    @patch.object(IndividualConfig, 'check_group_individual_update', new=False)
    def test_edit_individual_in_group_general_permission(self):
        individual, group, group_individual = create_group_with_individual(self.admin_user.username)
        query_str = f'''
            mutation {{
              editIndividualInGroup(
                input: {{
                  id: "{group_individual.id}"
                  groupId: "{group.id}"
                  individualId: "{individual.id}"
                  role: DAUGHTER
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # Anonymous User has no permission
        response = self.query(query_str)

        content = json.loads(response.content)
        internal_id = content['data']['editIndividualInGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['editIndividualInGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized'))

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['editIndividualInGroup']['internalId']
        self.assert_mutation_success(internal_id)

    @patch.object(IndividualConfig, 'check_group_individual_update', new=False)
    def test_edit_individual_in_group_row_security(self):
        individual, group, group_individual = create_group_with_individual(self.admin_user.username)
        individual_a, group_a, group_individual_a = create_group_with_individual(
            self.admin_user.username,
            group_override={'location': self.village_a},
            individual_override={'location': self.village_a},
        )
        individual_b, group_b, group_individual_b = create_group_with_individual(
            self.admin_user.username,
            group_override={'location': self.village_b},
            individual_override={'location': self.village_b},
        )
        query_str = f'''
            mutation {{
              editIndividualInGroup(
                input: {{
                  id: "{group_individual_a.id}"
                  groupId: "{group_a.id}"
                  individualId: "{individual_a.id}"
                  role: DAUGHTER
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot update individual in group for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['editIndividualInGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized.location'))

        # SP officer B can edit individual in group for district B
        query_str_b = query_str.replace(
            str(individual_a.id), str(individual_b.id)
        ).replace(
            str(group_a.id), str(group_b.id)
        ).replace(
            str(group_individual_a.id), str(group_individual_b.id)
        )
        response = self.query(
            query_str_b,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['editIndividualInGroup']['internalId']
        self.assert_mutation_success(internal_id)
        expected_gi = GroupIndividual.objects.filter(group_id=group_b.id, individual_id=individual_b.id)
        self.assertTrue(expected_gi.exists())
        self.assertEqual(expected_gi.first().id, group_individual_b.id)

        # SP officer A can edit individual in group for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['editIndividualInGroup']['internalId']
        self.assert_mutation_success(internal_id)
        expected_gi = GroupIndividual.objects.filter(group_id=group_a.id, individual_id=individual_a.id)
        self.assertTrue(expected_gi.exists())
        self.assertEqual(expected_gi.first().id, group_individual_a.id)

        # SP officer A can move individual without location to group in district A
        query_str_no_loc = query_str.replace(
            str(individual_a.id), str(individual.id)
        ).replace(
            str(group_individual_a.id), str(group_individual.id)
        )
        response = self.query(
            query_str_no_loc,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['editIndividualInGroup']['internalId']
        self.assert_mutation_success(internal_id)
        expected_gi = GroupIndividual.objects.filter(group_id=group_a.id, individual_id=individual.id)
        self.assertTrue(expected_gi.exists())
        self.assertNotEqual(expected_gi.first().id, group_individual.id)

        # Moving a individual to a group with different locations is not allowed
        query_str_updated = query_str.replace(str(group_individual_a.id), str(expected_gi.first().id))
        response = self.query(
            query_str_updated.replace(str(group_a.id), str(group_b.id)),
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['editIndividualInGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.individual_group_location_mismatch'))

        # SP officer A can move individual from district A to group without location
        response = self.query(
            query_str.replace(str(group_a.id), str(group.id)),
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['editIndividualInGroup']['internalId']
        self.assert_mutation_success(internal_id)
        expected_gi = GroupIndividual.objects.filter(group_id=group.id, individual_id=individual_a.id)
        self.assertTrue(expected_gi.exists())
        self.assertNotEqual(expected_gi.first().id, group_individual_a.id)

    def test_remove_individuals_from_group_general_permission(self):
        __, __, group_individual = create_group_with_individual(self.admin_user.username)
        query_str = f'''
            mutation {{
              removeIndividualFromGroup(
                input: {{
                  ids: ["{group_individual.id}"]
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # Anonymous User has no permission
        response = self.query(query_str)

        content = json.loads(response.content)
        internal_id = content['data']['removeIndividualFromGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['removeIndividualFromGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized'))

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['removeIndividualFromGroup']['internalId']
        self.assert_mutation_success(internal_id)

    def test_remove_individuals_from_group_row_security(self):
        individual, group, group_individual = create_group_with_individual(self.admin_user.username)
        individual_a, group_a, group_individual_a = create_group_with_individual(
            self.admin_user.username,
            group_override={'location': self.village_a},
            individual_override={'location': self.village_a},
        )
        individual_b, group_b, group_individual_b = create_group_with_individual(
            self.admin_user.username,
            group_override={'location': self.village_b},
            individual_override={'location': self.village_b},
        )
        query_str = f'''
            mutation {{
              removeIndividualFromGroup(
                input: {{
                  ids: ["{group_individual_a.id}"]
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot delete group for district A
        response = self.query(query_str)
        content = json.loads(response.content)
        internal_id = content['data']['removeIndividualFromGroup']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        internal_id = content['data']['removeIndividualFromGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized.location'))

        # SP officer A can delete group for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['removeIndividualFromGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # SP officer B can delete group without any district
        group_no_loc = create_group(self.admin_user.username)
        response = self.query(
            query_str.replace(
                str(group_individual_a.id),
                str(group_individual.id)
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['removeIndividualFromGroup']['internalId']
        self.assert_mutation_success(internal_id)

        # SP officer B cannot delete a mix of groups from district A and district B
        response = self.query(
            query_str.replace(
                f'["{group_individual_a.id}"]',
                f'["{group_individual_a.id}", "{group_individual_b.id}"]'
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['removeIndividualFromGroup']['internalId']
        self.assert_mutation_error(internal_id, _('unauthorized.location'))

        # SP officer B can delete group from district B
        group_no_loc = create_group(self.admin_user.username)
        response = self.query(
            query_str.replace(
                str(group_individual_a.id),
                str(group_individual_b.id)
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        internal_id = content['data']['removeIndividualFromGroup']['internalId']
        self.assert_mutation_success(internal_id)
