import json
from individual.tests.test_helpers import (
    create_individual,
    IndividualGQLTestCase,
)
from django.utils.translation import gettext as _


class IndividualGQLMutationTest(IndividualGQLTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_create_individual_general_permission(self):
        query_str = f'''
            mutation {{
              createIndividual(
                input: {{
                  firstName: "Alice"
                  lastName: "Foo"
                  dob: "2020-02-20"
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
        id = content['data']['createIndividual']['internalId']
        self.assert_mutation_error(id, _('mutation.authentication_required'))

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['createIndividual']['internalId']
        self.assert_mutation_success(id)

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['createIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized'))

    def test_create_individual_row_security(self):
        query_str = f'''
            mutation {{
              createIndividual(
                input: {{
                  firstName: "Alice"
                  lastName: "Foo"
                  dob: "2020-02-20"
                  locationId: {self.village_a.id}
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot create individual for district A
        response = self.query(query_str)
        content = json.loads(response.content)
        internal_id = content['data']['createIndividual']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        id = content['data']['createIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized.location'))

        # SP officer A can create individual for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['createIndividual']['internalId']
        self.assert_mutation_success(id)

        # SP officer B can create individual for district B
        response = self.query(
            query_str.replace(
                f'locationId: {self.village_a.id}',
                f'locationId: {self.village_b.id}'
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['createIndividual']['internalId']
        self.assert_mutation_success(id)

        # SP officer B can create individual without any district
        response = self.query(
            query_str.replace(f'locationId: {self.village_a.id}', ' '),
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['createIndividual']['internalId']
        self.assert_mutation_success(id)

    def test_update_individual_general_permission(self):
        individual = create_individual(self.admin_user.username)
        query_str = f'''
            mutation {{
              updateIndividual(
                input: {{
                  id: "{individual.id}"
                  firstName: "Bob"
                  lastName: "Bar"
                  dob: "2019-09-19"
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
        id = content['data']['updateIndividual']['internalId']
        self.assert_mutation_error(id, _('mutation.authentication_required'))

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['updateIndividual']['internalId']
        self.assert_mutation_success(id)

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['updateIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized'))

    def test_update_individual_row_security(self):
        individual_a = create_individual(
            self.admin_user.username,
            payload_override={'location': self.village_a},
        )
        query_str = f'''
            mutation {{
              updateIndividual(
                input: {{
                  id: "{individual_a.id}"
                  firstName: "Bob"
                  lastName: "Foo"
                  dob: "2020-02-19"
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot update individual for district A
        response = self.query(query_str)
        content = json.loads(response.content)
        internal_id = content['data']['updateIndividual']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        id = content['data']['updateIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized.location'))

        # SP officer A can update individual for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['updateIndividual']['internalId']
        self.assert_mutation_success(id)

        # SP officer B can update individual without any district
        individual_no_loc = create_individual(self.admin_user.username)
        response = self.query(
            query_str.replace(
                f'id: "{individual_a.id}"',
                f'id: "{individual_no_loc.id}"'
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['updateIndividual']['internalId']
        self.assert_mutation_success(id)


    def test_delete_individual_general_permission(self):
        individual1 = create_individual(self.admin_user.username)
        individual2 = create_individual(self.admin_user.username)
        query_str = f'''
            mutation {{
              deleteIndividual(
                input: {{
                  ids: ["{individual1.id}", "{individual2.id}"]
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
        id = content['data']['deleteIndividual']['internalId']
        self.assert_mutation_error(id, _('mutation.authentication_required'))

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['deleteIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized'))

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['deleteIndividual']['internalId']
        self.assert_mutation_success(id)

        # same for undo delete
        query_str = f'''
            mutation {{
              undoDeleteIndividual(
                input: {{
                  ids: ["{individual1.id}", "{individual2.id}"]
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
        id = content['data']['undoDeleteIndividual']['internalId']
        self.assert_mutation_error(id, _('mutation.authentication_required'))

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['undoDeleteIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized'))

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['undoDeleteIndividual']['internalId']
        self.assert_mutation_success(id)


    def test_delete_individual_row_security(self):
        individual_a1 = create_individual(
            self.admin_user.username,
            payload_override={'location': self.village_a},
        )
        individual_a2 = create_individual(
            self.admin_user.username,
            payload_override={'location': self.village_a},
        )
        individual_b = create_individual(
            self.admin_user.username,
            payload_override={'location': self.village_b},
        )
        query_str = f'''
            mutation {{
              deleteIndividual(
                input: {{
                  ids: ["{individual_a1.id}"]
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot delete individual for district A
        response = self.query(query_str)
        content = json.loads(response.content)
        internal_id = content['data']['deleteIndividual']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        id = content['data']['deleteIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized.location'))

        # SP officer A can delete individual for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['deleteIndividual']['internalId']
        self.assert_mutation_success(id)

        # SP officer B can delete individual without any district
        individual_no_loc = create_individual(self.admin_user.username)
        response = self.query(
            query_str.replace(
                str(individual_a1.id),
                str(individual_no_loc.id)
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['deleteIndividual']['internalId']
        self.assert_mutation_success(id)

        # SP officer B cannot delete a mix of individuals from district A and district B
        response = self.query(
            query_str.replace(
                f'["{individual_a1.id}"]',
                f'["{individual_a1.id}", "{individual_b.id}"]'
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['deleteIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized.location'))

        # SP officer B can delete individual from district B
        individual_no_loc = create_individual(self.admin_user.username)
        response = self.query(
            query_str.replace(
                str(individual_a1.id),
                str(individual_b.id)
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['deleteIndividual']['internalId']
        self.assert_mutation_success(id)

        # same for undo delete
        query_str = f'''
            mutation {{
              undoDeleteIndividual(
                input: {{
                  ids: ["{individual_a1.id}"]
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # SP officer B cannot undelete individual for district A
        response = self.query(query_str)
        content = json.loads(response.content)
        internal_id = content['data']['undoDeleteIndividual']['internalId']
        self.assert_mutation_error(internal_id, _('mutation.authentication_required'))
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        id = content['data']['undoDeleteIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized.location'))

        # SP officer A can undelete individual for district A
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['undoDeleteIndividual']['internalId']
        self.assert_mutation_success(id)

        # SP officer B can undelete individual without any district
        response = self.query(
            query_str.replace(
                str(individual_a1.id),
                str(individual_no_loc.id)
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['undoDeleteIndividual']['internalId']
        self.assert_mutation_success(id)

        # SP officer B cannot undelete a mix of individuals from district A and district B
        response = self.query(
            query_str.replace(
                f'["{individual_a1.id}"]',
                f'["{individual_a1.id}", "{individual_b.id}"]'
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['undoDeleteIndividual']['internalId']
        self.assert_mutation_error(id, _('unauthorized.location'))

        # SP officer B can undelete individual from district B
        response = self.query(
            query_str.replace(
                str(individual_a1.id),
                str(individual_b.id)
            ), headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['undoDeleteIndividual']['internalId']
        self.assert_mutation_success(id)
